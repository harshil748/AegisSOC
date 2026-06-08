import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Runs `fetcher` whenever `deps` change, wiring up an AbortController so
 * stale requests never clobber fresher state. `fetcher` receives the
 * abort signal to forward to the API client.
 */
export function useAsync<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[],
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const nonce = useRef(0);

  const run = useCallback(() => {
    const controller = new AbortController();
    const myNonce = ++nonce.current;
    setLoading(true);
    setError(null);
    fetcher(controller.signal)
      .then((res) => {
        if (myNonce !== nonce.current) return;
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        if (controller.signal.aborted || myNonce !== nonce.current) return;
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Something went wrong.";
        setError(message);
        setLoading(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => run(), [run]);

  const refetch = useCallback(() => {
    run();
  }, [run]);

  return { data, loading, error, refetch };
}
