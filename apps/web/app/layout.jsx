import './globals.css';

export const metadata = {
  title: 'Grok Invoices — Dashboard',
  description: 'Invoice decisions, client questions, and company context in one workspace.',
  icons: { icon: '/assets/logo-v2.png', apple: '/assets/logo-v2.png' },
};

export default function RootLayout({ children }) {
  return <html lang="en"><body>
    <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2">Skip to content</a>
    {children}
  </body></html>;
}
