'use client';

import { BotLog } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse'
import styles from './botLog.module.css'

export function BotLogCard({ botLog }: { botLog: BotLog }) {
  return (
    <div className={`${styles.botLogCardContainer}`}>
      <h1>${botLog.text}</h1>
    </div>
  );
}
