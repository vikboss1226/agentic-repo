import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the app heading', () => {
  render(<App />);
  const heading = screen.getByText(/weather now/i);
  expect(heading).toBeInTheDocument();
});
