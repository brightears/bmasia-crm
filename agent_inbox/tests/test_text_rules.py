"""Characters that change how text looks without showing are refused; normal Thai is kept."""
import pytest

from agent_inbox.tests.conftest import ACTIVITIES, PROPOSALS, activity_body, token_client
from agent_inbox.validation import has_control

THAI_ADDRESS = 'ถนนสุขุมวิท ซอย 11 แขวงคลองเตยเหนือ'  # letters with vowel and tone marks
THAI_NAME = 'คุณสมศักดิ์ ใจดี'


@pytest.mark.parametrize('text', [THAI_ADDRESS, THAI_NAME, 'Café Zoë', 'नमस्ते', 'می‌خواهم'])
def test_ordinary_text_in_any_script_is_accepted(text):
    assert has_control(text) is False


@pytest.mark.parametrize('char', [
    '‮', '‪', '‫', '‬', '‭', '⁦', '⁧', '⁨', '⁩',
    '​', '‎', '‏', '⁠', '﻿', '­', '\x00', '\x07', ' ', ' ', '',
])
def test_invisible_and_direction_characters_are_refused_in_single_line_values(char):
    assert has_control(f'Room{char}12') is True


def test_joiners_are_kept_only_inside_words_of_scripts_that_use_them():
    assert has_control('می‌خواهم') is False   # zero-width non-joiner inside a Persian word
    assert has_control('ab‍cd') is True       # between ASCII letters
    assert has_control('‍start') is True
    assert has_control('สวัสดี‍') is True


def test_bodies_copied_from_a_source_may_keep_format_characters():
    text = 'Thai mail​with a zero-width space'
    assert has_control(text, allow_newlines=True, allow_format=True) is False
    assert has_control('bell\x07', allow_newlines=True, allow_format=True) is True


@pytest.mark.parametrize('field', ['address_line1', 'city', 'phone'])
def test_patch_values_with_hidden_characters_are_refused(agent, company, field):
    response = token_client(agent).post(PROPOSALS, {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {field: '9 Example‮Road'}, 'evidence_quote': 'q',
    }, format='json')
    assert response.status_code == 400 and 'invisible' in response.json()['detail']


def test_patch_values_with_control_characters_are_refused(agent, company):
    response = token_client(agent).post(PROPOSALS, {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'city': 'Bang\x07kok'}, 'evidence_quote': 'q',
    }, format='json')
    assert response.status_code == 400


def test_thai_patch_values_are_accepted(agent, company):
    response = token_client(agent).post(PROPOSALS, {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'address_line1': THAI_ADDRESS}, 'evidence_quote': 'q',
    }, format='json')
    assert response.status_code == 201, response.content


def test_activity_summary_refuses_hidden_characters_but_body_keeps_them(agent, company):
    client = token_client(agent)
    refused = client.post(ACTIVITIES, activity_body(company, summary='Call​ back'), format='json')
    assert refused.status_code == 400
    kept = client.post(ACTIVITIES, activity_body(company, body='ข้อความ​จากลูกค้า'), format='json')
    assert kept.status_code == 201


@pytest.mark.parametrize('text', [
    'Team \U0001F468\u200d\U0001F469\u200d\U0001F467',          # family emoji sequence
    'Dr \U0001F469\u200d\u2695\ufe0f',                            # profession emoji with variation selector
    'Fans \U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F',  # subdivision flag
    'Bangkok \U0001F1F9\U0001F1ED',                                  # country flag
    'Café \U0001F44D\U0001F3FD',                                     # skin-tone modifier
])
def test_emoji_sequences_and_flags_are_accepted_in_names(text):
    assert has_control(text) is False


@pytest.mark.parametrize('text', [
    'Room\u061c12', 'Room\u202e21', 'Room\u2066x\u2069', 'ab\u200dcd', 'Fans \U000E0067\U000E007F',
    '\U000E007F', 'ok\u200d', 'Hotel\u2060X',
])
def test_direction_controls_and_stray_joiners_or_tags_are_refused(text):
    assert has_control(text) is True
