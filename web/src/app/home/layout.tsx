'use client';

import styles from './layout.module.css';
import HomeSidebar from '@/app/home/components/home-sidebar/HomeSidebar';
import HomeTitleBar from '@/app/home/components/home-titlebar/HomeTitleBar';
import React, { useState, useEffect } from 'react';
import { SidebarChildVO } from '@/app/home/components/home-sidebar/HomeSidebarChild';

export default function HomeLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [title, setTitle] = useState<string>('');
  const [subtitle, setSubtitle] = useState<string>('');
  const [helpLink, setHelpLink] = useState<string>('');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);
  const [isMobile, setIsMobile] = useState<boolean>(false);

  useEffect(() => {
    const checkIfMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    checkIfMobile();
    window.addEventListener('resize', checkIfMobile);
    return () => window.removeEventListener('resize', checkIfMobile);
  }, []);

  const onSelectedChangeAction = (child: SidebarChildVO) => {
    setTitle(child.name);
    setSubtitle(child.description);
    setHelpLink(child.helpLink);
    if (isMobile) {
      setIsMobileMenuOpen(false);
    }
  };

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  return (
    <div className={styles.homeLayoutContainer}>
      <aside
        className={`${styles.sidebar} ${isMobileMenuOpen ? styles.sidebarOpen : ''}`}
      >
        <HomeSidebar onSelectedChangeAction={onSelectedChangeAction} />
      </aside>

      <div className={styles.main}>
        <HomeTitleBar
          title={title}
          subtitle={subtitle}
          helpLink={helpLink}
          onMenuToggle={toggleMobileMenu}
        />

        <main className={styles.mainContent}>{children}</main>
      </div>
    </div>
  );
}
