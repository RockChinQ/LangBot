import { httpClient } from '@/app/infra/http/HttpClient';
import { GetBotLogsRequest } from '@/app/infra/http/requestParam/bots/GetBotLogsRequest';
import {
  BotLog,
  GetBotLogsResponse,
} from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';

export class BotLogManager {
  private botId: string;
  private callbacks: ((_: BotLog[]) => void)[] = [];
  private intervalIds: number[] = [];

  constructor(botId: string) {
    this.botId = botId;
  }

  startListenServerPush() {
    const timerNumber = setInterval(() => {
      this.getLogList(-1, 50).then((response) => {
        this.callbacks.forEach((callback) =>
          callback(this.parseResponse(response)),
        );
      });
    }, 3000);
    this.intervalIds.push(Number(timerNumber));
  }

  stopServerPush() {
    this.intervalIds.forEach((id) => clearInterval(id));
  }

  subscribeLogPush(callback: (_: BotLog[]) => void) {
    this.callbacks.push(callback);
  }

  unsubscribeLogPush(callback: () => void) {
    this.callbacks = this.callbacks.filter((cb) => cb !== callback);
  }

  dispose() {
    this.callbacks = [];
  }

  /**
   * 获取日志页的基本信息
   */
  private getLogList(next: number, count: number = 50) {
    return httpClient.getBotLogs(this.botId, {
      from_index: next,
      max_count: count,
    });
  }

  async loadFirstPage() {
    return this.parseResponse(await this.getLogList(-1));
  }

  async loadMore(position: number) {
    return this.parseResponse(await this.getLogList(position));
  }

  getLogVOList() {}

  private parseResponse(httpResponse: GetBotLogsResponse): BotLog[] {
    console.log("parse bot log: ", httpResponse)
    return httpResponse.logs;
  }
}
