// Jest setup (loaded automatically by react-scripts before each test file).
// React Router 7 needs TextEncoder/TextDecoder, which the Jest 27 jsdom environment lacks.
import { TextDecoder, TextEncoder } from 'util';

Object.assign(globalThis, { TextEncoder, TextDecoder });
import '@testing-library/jest-dom';
