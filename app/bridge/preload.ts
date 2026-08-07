import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron'

type SetupCompletePayload = { apiPort: number }
type UserContext = { platform: string; userDomain: string; username: string }

function subscribe<T>(channel: string, callback: (payload: T) => void) {
  const listener = (_event: IpcRendererEvent, payload: T) => callback(payload)
  ipcRenderer.on(channel, listener)
  return () => ipcRenderer.removeListener(channel, listener)
}

const xerAgent = {
  onSetupStatus: (callback: (message: string) => void) => subscribe('setup-status', callback),
  onSetupError: (callback: (message: string) => void) => subscribe('setup-error', callback),
  onSetupComplete: (callback: (payload: SetupCompletePayload) => void) => subscribe('setup-complete', callback),
  getUserContext: (): Promise<UserContext> => ipcRenderer.invoke('get-user-context'),
  getAppVersion: (): Promise<string> => ipcRenderer.invoke('get-app-version'),
}

export type XerAgentBridge = typeof xerAgent

contextBridge.exposeInMainWorld('xerAgent', xerAgent)
