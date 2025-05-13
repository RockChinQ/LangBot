'use client';

import styles from './HomeSidebar.module.css';
import { useEffect, useState } from 'react';
import {
  SidebarChild,
  SidebarChildVO,
} from '@/app/home/components/home-sidebar/HomeSidebarChild';
import { useRouter, usePathname } from 'next/navigation';
import { sidebarConfigList } from '@/app/home/components/home-sidebar/sidbarConfigList';
import langbotIcon from '@/app/assets/langbot-logo.webp';
import { httpClient } from '@/app/infra/http/HttpClient';
import { LogOut, User } from 'lucide-react';

// TODO 侧边导航栏要加动画
export default function HomeSidebar({
  onSelectedChangeAction,
}: {
  onSelectedChangeAction: (sidebarChild: SidebarChildVO) => void;
}) {
  // 路由相关
  const router = useRouter();
  const pathname = usePathname();
  // 路由被动变化时处理
  useEffect(() => {
    handleRouteChange(pathname);
  }, [pathname]);

  const [selectedChild, setSelectedChild] = useState<SidebarChildVO>();
  const [userEmail, setUserEmail] = useState<string>('');

  useEffect(() => {
    console.log('HomeSidebar挂载完成');
    initSelect();
    
    if (!localStorage.getItem('token')) {
      localStorage.setItem('token', 'test-token');
      localStorage.setItem('userEmail', 'test@example.com');
    }
    
    const email = localStorage.getItem('userEmail');
    if (email) {
      setUserEmail(email);
    }
    return () => console.log('HomeSidebar卸载');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleChildClick(child: SidebarChildVO) {
    setSelectedChild(child);
    handleRoute(child);
    onSelectedChangeAction(child);
  }

  function initSelect() {
    // 根据当前路径选择对应的菜单项
    const currentPath = pathname;
    const matchedChild = sidebarConfigList.find(
      (childConfig) => childConfig.route === currentPath,
    );
    if (matchedChild) {
      handleChildClick(matchedChild);
    } else {
      // 如果没有匹配的路径，则默认选择第一个
      handleChildClick(sidebarConfigList[0]);
    }
  }

  function handleRoute(child: SidebarChildVO) {
    console.log(child);
    router.push(`${child.route}`);
  }

  function handleRouteChange(pathname: string) {
    // TODO 这段逻辑并不好，未来router封装好后改掉
    // 判断在home下，并且路由更改的是自己的路由子组件则更新UI
    const routeList = pathname.split('/');
    if (
      routeList[1] === 'home' &&
      sidebarConfigList.find((childConfig) => childConfig.route === pathname)
    ) {
      console.log('find success');
      const routeSelectChild = sidebarConfigList.find(
        (childConfig) => childConfig.route === pathname,
      );
      if (routeSelectChild) {
        setSelectedChild(routeSelectChild);
      }
    }
  }
  
  function handleLogout() {
    localStorage.removeItem('token');
    localStorage.removeItem('userEmail');
    window.location.href = '/login';
  }

  return (
    <div className={`${styles.sidebarContainer}`}>
      <div className={`${styles.sidebarTopContainer}`}>
        {/* LangBot、ICON区域 */}
        <div className={`${styles.langbotIconContainer}`}>
          {/* icon */}
          <img
            className={`${styles.langbotIcon}`}
            src={langbotIcon.src}
            alt="langbot-icon"
          />
          {/* 文字 */}
          <div className={`${styles.langbotTextContainer}`}>
            <div className={`${styles.langbotText}`}>LangBot</div>
            <div className={`${styles.langbotVersion}`}>
              {httpClient.systemInfo?.version}
            </div>
          </div>
        </div>
        {/* 菜单列表，后期可升级成配置驱动 */}
        <div>
          {sidebarConfigList.map((config) => {
            return (
              <div
                key={config.id}
                onClick={() => {
                  console.log('click:', config.id);
                  handleChildClick(config);
                }}
              >
                <SidebarChild
                  onClick={() => {}}
                  isSelected={
                    selectedChild !== undefined &&
                    selectedChild.id === config.id
                  }
                  icon={config.icon}
                  name={config.name}
                />
              </div>
            );
          })}
        </div>
      </div>

      <div className={`${styles.sidebarBottomContainer}`}>
        {userEmail && (
          <SidebarChild
            onClick={() => {}}
            isSelected={false}
            icon={<User className={`${styles.sidebarChildIcon}`} />}
            name={userEmail}
          />
        )}
        <SidebarChild
          onClick={handleLogout}
          isSelected={false}
          icon={<LogOut className={`${styles.sidebarChildIcon}`} />}
          name="退出登录"
        />
        <SidebarChild
          onClick={() => {
            // open docs.langbot.app
            window.open('https://docs.langbot.app', '_blank');
          }}
          isSelected={false}
          icon={
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22ZM12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM11 15H13V17H11V15ZM13 13.3551V14H11V12.5C11 11.9477 11.4477 11.5 12 11.5C12.8284 11.5 13.5 10.8284 13.5 10C13.5 9.17157 12.8284 8.5 12 8.5C11.2723 8.5 10.6656 9.01823 10.5288 9.70577L8.56731 9.31346C8.88637 7.70919 10.302 6.5 12 6.5C13.933 6.5 15.5 8.067 15.5 10C15.5 11.5855 14.4457 12.9248 13 13.3551Z"></path>
            </svg>
          }
          name="帮助文档"
        />
      </div>
    </div>
  );
}
