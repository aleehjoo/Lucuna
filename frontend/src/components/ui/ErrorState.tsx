import { Button } from "./Button";

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-[var(--border)] px-6 py-12 text-center">
      <p className="text-sm font-medium text-[var(--oxblood)]">{message}</p>
      {onRetry ? (
        <Button variant="ghost" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
