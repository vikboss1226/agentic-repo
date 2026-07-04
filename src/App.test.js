import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the comments heading', () => {
  render(<App />);
  const heading = screen.getByText(/comments from jsonplaceholder/i);
  expect(heading).toBeInTheDocument();
});
