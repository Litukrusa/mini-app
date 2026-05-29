import { useState } from "react";
import {
  Panel,
  PanelHeader,
  PanelHeaderBack,
  Group,
  Placeholder,
  Button,
  FormItem,
  Input,
} from "@vkontakte/vkui";
import { eiosLogin } from "../api";

const INTRO =
  "Для части групп ДГТУ (например, ИПБТ11) API без входа в ЭИОС отдаёт неполное расписание.\n\n" +
  "Логин и пароль — те же, что в личном кабинете edu.donstu.ru. " +
  "Данные хранятся на сервере в зашифрованном виде.";

export function EiosAuthPanel({ onBack, onDone }) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setError("");
    if (!login.trim() || !password.trim()) {
      setError("Введите логин и пароль");
      return;
    }
    setLoading(true);
    try {
      const data = await eiosLogin(login.trim(), password);
      onDone(data.me);
    } catch (e) {
      setError(e.message || "Ошибка входа");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel id="eios-auth">
      <PanelHeader before={<PanelHeaderBack onClick={onBack} />}>
        ЭИОС
      </PanelHeader>

      <Group>
        <Placeholder header="Дополнительная авторизация">{INTRO}</Placeholder>
      </Group>

      <Group>
        <FormItem top="Логин ЭИОС">
          <Input
            type="text"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            placeholder="Как на edu.donstu.ru"
            autoComplete="username"
          />
        </FormItem>
        <FormItem top="Пароль">
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Пароль"
            autoComplete="current-password"
          />
        </FormItem>
        {error ? (
          <div
            style={{
              padding: "0 16px 8px",
              color: "var(--vkui--color_text_negative)",
              fontSize: 14,
            }}
          >
            {error}
          </div>
        ) : null}
        <div style={{ padding: "8px 16px 16px" }}>
          <Button size="l" stretched onClick={submit} loading={loading}>
            Войти
          </Button>
        </div>
      </Group>
    </Panel>
  );
}
