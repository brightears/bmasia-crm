"""One rule for turning a caught exception into log output without a mail server's reply.

A mail server's raw reply can echo what it was sent, including a password. It travels in
``smtplib`` exceptions (and in connection errors), in their text and in their traceback.
It can also travel attached to another exception: ``raise RuntimeError(...) from smtp_error``
sets ``__cause__``, and an error raised while handling a mail error carries it as
``__context__``. Python's traceback formatting prints every link of that chain.

So an exception is *mail-tainted* when any link of its chain is a mail error: the
exception itself, its ``__cause__``, its ``__context__`` (unless suppressed with
``raise ... from None``), recursively, and the members of an ``ExceptionGroup``.

``log_exception`` logs:
- a mail error: its fixed description (type, SMTP code, short text); no traceback;
- a tainted non-mail error (a bug that happened around a mail error): its type, its message
  (only its type when the message repeats the mail error's text) and its OWN frames as
  text, formatted without the chain, plus the mail link's fixed description; never the
  chain and never ``exc_info``;
- any other error: type, message and the full traceback via ``exc_info``. No link of such
  a chain is a mail error, so its traceback cannot contain a mail server's reply.

``safe_exception_message`` is the matching rule for text shown to users or stored.
crm_app/services/email_service.py, crm_app/api_errors.py and
crm_app/services/invoice_payments.py use these functions.
"""
import logging
import smtplib
import traceback

_DESCRIPTIONS = (
    (smtplib.SMTPAuthenticationError, 'the mail server did not accept the login'),
    (smtplib.SMTPSenderRefused, 'the mail server refused the sender address'),
    (smtplib.SMTPRecipientsRefused, 'the mail server refused the recipients'),
    (smtplib.SMTPDataError, 'the mail server refused the message'),
    (smtplib.SMTPConnectError, 'the mail server refused the connection'),
    (smtplib.SMTPServerDisconnected, 'the mail server closed the connection'),
    (smtplib.SMTPNotSupportedError, 'the mail server does not support a required command'),
    (smtplib.SMTPException, 'the mail server refused the request'),
    (OSError, 'could not connect to the mail server'),
)


def describe_mail_exception(exc):
    """A log-safe description of a mail error: type, SMTP code and a fixed text, or None."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return f'{type(exc).__name__}: {_refused_recipients_text(exc)}'
    for kind, text in _DESCRIPTIONS:
        if isinstance(exc, kind):
            code = getattr(exc, 'smtp_code', None)
            code_text = f' (SMTP code {code})' if isinstance(code, int) else ''
            return f'{type(exc).__name__}{code_text}: {text}'
    return None


def _refused_recipients_text(exc):
    """'the mail server refused N recipient(s) (example.com: 550; ...)': domain and code only."""
    recipients = getattr(exc, 'recipients', None) or {}
    parts = []
    for address, reply in sorted(recipients.items(), key=lambda item: str(item[0])):
        address = str(address)
        domain = address.rsplit('@', 1)[-1] if '@' in address else 'unknown domain'
        code = reply[0] if isinstance(reply, (tuple, list)) and reply and isinstance(reply[0], int) else None
        parts.append(f'{domain}: {code if code is not None else "no code"}')
    detail = f" ({'; '.join(parts)})" if parts else ''
    return f'the mail server refused {len(recipients)} recipient(s){detail}'


def exception_chain(exc):
    """Every exception linked to ``exc``: itself, causes, unsuppressed contexts, group members."""
    seen = set()
    order = []
    pending = [exc]
    while pending:
        current = pending.pop(0)
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        order.append(current)
        pending.append(current.__cause__)
        if not current.__suppress_context__:
            pending.append(current.__context__)
        members = getattr(current, 'exceptions', None)  # ExceptionGroup
        if isinstance(current, BaseException) and isinstance(members, (list, tuple)):
            pending.extend(m for m in members if isinstance(m, BaseException))
    return order


def mail_link(exc):
    """The first mail error in the chain of ``exc`` (possibly ``exc`` itself), or None."""
    for link in exception_chain(exc):
        if describe_mail_exception(link) is not None:
            return link
    return None


def _reply_fragments(mail_error):
    """Pieces of text that would reveal a mail error's reply if repeated elsewhere."""
    fragments = [str(mail_error), repr(mail_error)]
    for attribute in ('smtp_error', 'strerror'):
        value = getattr(mail_error, attribute, None)
        if isinstance(value, bytes):
            fragments += [value.decode('utf-8', 'replace'), repr(value)]
        elif isinstance(value, str):
            fragments.append(value)
    for arg in getattr(mail_error, 'args', ()):
        if isinstance(arg, bytes):
            fragments += [arg.decode('utf-8', 'replace'), repr(arg)]
        elif isinstance(arg, str):
            fragments.append(arg)
    for reply in (getattr(mail_error, 'recipients', None) or {}).values():
        if isinstance(reply, (tuple, list)):
            for part in reply:
                if isinstance(part, bytes):
                    fragments += [part.decode('utf-8', 'replace'), repr(part)]
                elif isinstance(part, str):
                    fragments.append(part)
    return [f for f in fragments if f and len(f) >= 4]


def safe_exception_message(exc):
    """The message of a non-mail exception, or only its type when it repeats a chained mail error's text."""
    message = str(exc)
    link = mail_link(exc)
    if link is None or link is exc:
        return message
    own_text = ' '.join([message, repr(exc.args)])
    if any(fragment in own_text for fragment in _reply_fragments(link)):
        return type(exc).__name__
    return message


def describe_exception(exc):
    """One-line, log-safe text: a mail error's description, else 'Type: message' (see above)."""
    described = describe_mail_exception(exc)
    if described is not None:
        return described
    text = f'{type(exc).__name__}: {safe_exception_message(exc)}'
    link = mail_link(exc)
    if link is not None:
        text += f' (while handling {describe_mail_exception(link)})'
    return text


def own_frames_text(exc):
    """The traceback of ``exc`` alone (no __cause__/__context__), ending with a safe 'Type: message' line."""
    frames = ''.join(traceback.format_tb(exc.__traceback__)) if exc.__traceback__ else ''
    return f'Traceback (most recent call last, chained exceptions not shown):\n{frames}{describe_exception(exc)}'


def log_exception(logger, message, exc, mail_level=logging.ERROR, bug_level=logging.ERROR):
    """Log ``exc`` after ``message`` (plain text) by the rule in the module docstring."""
    if describe_mail_exception(exc) is not None:
        logger.log(mail_level, '%s: %s', message, describe_mail_exception(exc))
    elif mail_link(exc) is not None:
        logger.log(bug_level, '%s: %s\n%s', message, describe_exception(exc), own_frames_text(exc))
    else:
        logger.log(bug_level, '%s: %s: %s', message, type(exc).__name__, exc,
                   exc_info=(type(exc), exc, exc.__traceback__))
