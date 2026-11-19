import { summarizeBulkDelete } from './bulkResults';

test('a bulk delete where every record was refused does not read as success', () => {
  const reply = {
    message: '0 records deleted', deleted: 0,
    results: [{ id: 'a', deleted: false, error: 'Welcome cannot be deleted: 2 campaigns refer to it.' }],
  };
  expect(summarizeBulkDelete(reply, 'template')).toEqual({
    success: '',
    error: '1 template not deleted: Welcome cannot be deleted: 2 campaigns refer to it.',
  });
});

test('a mixed result reports both parts', () => {
  const reply = {
    deleted: 2,
    results: [{ id: 'a', deleted: true }, { id: 'b', deleted: true }, { id: 'c', deleted: false, error: 'Not found.' }],
  };
  expect(summarizeBulkDelete(reply, 'template')).toEqual({
    success: '2 templates deleted', error: '1 template not deleted: Not found.',
  });
});
