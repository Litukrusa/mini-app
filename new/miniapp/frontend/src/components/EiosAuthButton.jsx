import { Button } from "@vkontakte/vkui";

export function EiosAuthButton({ me, onConnect, onDisconnect }) {
  if (!me?.eiosAvailable) {
    return null;
  }

  const authenticated = Boolean(me.eiosAuthenticated);
  const canConfigure = me.eiosCanConfigure !== false;

  return (
    <div style={{ padding: "8px 16px 0" }}>
      <Button
        size="l"
        stretched
        mode={authenticated ? "secondary" : "primary"}
        disabled={!authenticated && !canConfigure}
        onClick={authenticated ? onDisconnect : onConnect}
      >
        {authenticated ? "🔓 Отключить доп. авторизацию" : "🔐 Дополнительная авторизация"}
      </Button>
      {!canConfigure && !authenticated && (
        <p
          style={{
            margin: "8px 0 0",
            fontSize: 13,
            color: "var(--vkui--color_text_secondary)",
          }}
        >
          На сервере не задан EIOS_ENCRYPTION_KEY — сохранение логина недоступно.
        </p>
      )}
    </div>
  );
}
