import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the comments heading', () => {
  render(<App />);
  const heading = screen.getByText(/Loading comments.../i);
  expect(heading).toBeInTheDocument();
});