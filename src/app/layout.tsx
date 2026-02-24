import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Transparence Nationale | Patrimoine des Élus Français',
  description: 'Explorez le patrimoine et les revenus des élus français via les données HATVP',
  keywords: ['HATVP', 'élus', 'patrimoine', 'transparence', 'France', 'politique'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body className={inter.className}>
        <header className="bg-white shadow-sm border-b sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <a href="/" className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-green-500 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-xl">TN</span>
                </div>
                <div>
                  <h1 className="text-xl font-bold text-gray-900">
                    Transparence Nationale
                  </h1>
                  <p className="text-xs text-gray-500">
                    Données HATVP
                  </p>
                </div>
              </a>
              <nav className="hidden sm:flex gap-4">
                <a 
                  href="https://www.hatvp.fr" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-sm text-gray-600 hover:text-blue-600 transition-colors"
                >
                  HATVP
                </a>
                <a 
                  href="https://github.com" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-sm text-gray-600 hover:text-blue-600 transition-colors"
                >
                  GitHub
                </a>
              </nav>
            </div>
          </div>
        </header>
        
        <main className="min-h-screen">
          {children}
        </main>

        <footer className="bg-gray-900 text-white py-8 mt-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center">
              <p className="text-sm text-gray-400">
                © 2024 Transparence Nationale - Données issues de la{' '}
                <a 
                  href="https://www.hatvp.fr" 
                  className="text-blue-400 hover:underline"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Haute Autorité pour la Transparence de la Vie Publique
                </a>
              </p>
              <p className="text-xs text-gray-500 mt-2">
                Projet open-source à des fins de transparence démocratique
              </p>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
