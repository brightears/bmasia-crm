import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import Tasks from './Tasks';
import ApiService from '../services/api';

jest.mock('../services/authService', () => ({ __esModule: true, default: {}, authApi: {} }));
jest.mock('../components/TaskKanbanBoard', () => ({ __esModule: true, default: () => null }));
jest.mock('../components/TaskListView', () => ({ __esModule: true, default: () => null }));
jest.mock('../components/TaskForm', () => ({
  __esModule: true,
  default: ({ open, task }: any) => (open ? <div>editing {task?.title}</div> : null),
}));
jest.mock('../components/TaskDetail', () => ({
  __esModule: true,
  default: ({ open, task, onClose, onEdit, onDelete }: any) =>
    open ? (
      <div role="dialog">
        <span>{task.title}</span>
        <button onClick={onClose}>Close</button>
        <button onClick={onEdit}>Edit</button>
        <button onClick={() => onDelete(task.id)}>Delete</button>
      </div>
    ) : null,
}));
jest.mock('../services/api', () => {
  const empty = () => Promise.resolve({ results: [] });
  return {
    __esModule: true,
    default: {
      getTasks: empty,
      getUsers: empty,
      getOpportunities: empty,
      getContracts: empty,
      getContacts: empty,
      getCompaniesSimple: () => Promise.resolve([]),
      getTask: jest.fn(),
      deleteTask: jest.fn(() => Promise.resolve()),
    },
  };
});

const api = ApiService as any;
let location: any;
const Where: React.FC = () => {
  location = useLocation();
  return null;
};

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Where />
      <Routes>
        <Route path="/tasks" element={<Tasks />} />
        <Route path="/tasks/:id" element={<Tasks />} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  api.getTask.mockResolvedValue({ id: 't-1', title: 'Call back the GM', status: 'To Do' });
});

const openAndClick = async (button: string) => {
  renderAt('/tasks/t-1');
  expect(await screen.findByRole('dialog')).toHaveTextContent('Call back the GM');
  expect(api.getTask).toHaveBeenCalledWith('t-1');
  fireEvent.click(screen.getByRole('button', { name: button }));
  await waitFor(() => expect(location.pathname).toBe('/tasks'));
  expect(screen.queryByRole('dialog')).toBeNull();
};

it('leaves /tasks/:id when the task is closed', async () => {
  await openAndClick('Close');
});

it('leaves /tasks/:id when the task is edited, keeping the form open', async () => {
  await openAndClick('Edit');
  expect(screen.getByText('editing Call back the GM')).toBeInTheDocument();
});

it('leaves /tasks/:id when the task is deleted', async () => {
  await openAndClick('Delete');
  expect(api.deleteTask).toHaveBeenCalledWith('t-1');
});
