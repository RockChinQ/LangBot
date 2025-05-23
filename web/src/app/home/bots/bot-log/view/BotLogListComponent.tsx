'use client';

import { BotLogManager } from '@/app/home/bots/bot-log/BotLogManager';
import { useEffect, useState } from 'react';
import { BotLog } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';
import { BotLogCard } from '@/app/home/bots/bot-log/view/BotLogCard';
import styles from './botLog.module.css';

export function BotLogListComponent({ botId }: { botId: string }) {
  const manager = new BotLogManager(botId);
  const [botLogList, setBotLogList] = useState<BotLog[]>([]);
  const [autoFlush, setAutoFlush] = useState(true);

  useEffect(() => {
    initComponent();
  }, []);

  function initComponent() {
    // 订阅日志推送
    manager.subscribeLogPush(handleBotLogPush);
    // 加载第一页日志
    manager.loadFirstPage().then((response) => {
      setBotLogList(response);
    });
  }

  function loadMore() {
    // 加载更多日志
    manager.loadMore(botLogList.length).then((response) => {
      setBotLogList([...botLogList, ...response]);
    });
  }

  function handleBotLogPush(response: BotLog[]) {
    setBotLogList(response);
  }
  return (
    <div className={`${styles.botLogListContainer}`}>
      {botLogList.map((botLog) => {
        return <BotLogCard botLog={botLog} key={botLog.seq_id} />;
      })}
    </div>
  );
}
