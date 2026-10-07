import { createContext, useContext } from 'react';

interface AppContextValue {
  demoMode: boolean;
  setDemoMode: (v: boolean) => void;
  redactMode: boolean;
  setRedactMode: (v: boolean) => void;
}

export const AppContext = createContext<AppContextValue>({
  demoMode: false,
  setDemoMode: () => {},
  redactMode: false,
  setRedactMode: () => {},
});

export function useAppContext() {
  return useContext(AppContext);
}
