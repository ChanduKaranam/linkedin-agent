import React from 'react';
import Navbar from './Navbar';
import { motion, AnimatePresence } from 'motion/react';
import { useLocation } from 'react-router-dom';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="h-screen overflow-hidden flex flex-col bg-background selection:bg-black selection:text-white">
      <Navbar />
      <main className="flex-1 min-h-0 flex overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="flex-1 min-h-0 flex overflow-hidden"
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
