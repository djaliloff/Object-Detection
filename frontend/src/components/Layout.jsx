import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import GlobalAlertListener from './GlobalAlertListener';

const Layout = () => {
  return (
    <div className="flex h-screen bg-gray-950">
      {/* Global headless WS listener — mounts once for the whole session */}
      <GlobalAlertListener />

      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-x-hidden overflow-y-auto bg-gray-950">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
