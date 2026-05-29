import {
  Panel,
  PanelHeader,
  PanelHeaderBack,
  Group,
  Header,
  Cell,
  Placeholder,
  Button,
} from "@vkontakte/vkui";
import { setUniversity, resetProfile } from "../api";
import { EiosAuthButton } from "../components/EiosAuthButton";

export function SettingsPanel({
  me,
  onBack,
  onRefresh,
  onPickGroup,
  onOpenEios,
  onEiosLogout,
}) {
  const univ = me?.university;

  const pick = async (code) => {
    await setUniversity(code);
    await onRefresh();
  };

  const onReset = async () => {
    if (!confirm("Сбросить все настройки?")) return;
    await resetProfile();
    onRefresh();
  };

  return (
    <Panel id="settings">
      <PanelHeader before={<PanelHeaderBack onClick={onBack} />}>
        Настройки
      </PanelHeader>

      <Group>
        <Header mode="secondary">Вуз</Header>
        <Cell onClick={() => pick("T")} indicator={univ === "T" ? "✓" : null}>
          ПИ ДГТУ
        </Cell>
        <Cell onClick={() => pick("D")} indicator={univ === "D" ? "✓" : null}>
          ДГТУ
        </Cell>
        <EiosAuthButton me={me} onConnect={onOpenEios} onDisconnect={onEiosLogout} />
      </Group>

      {!univ && (
        <Group>
          <Placeholder>Выберите вуз — затем внизу откройте «Профиль» и нажмите «Выбрать группу»</Placeholder>
        </Group>
      )}

      {univ && (
        <Group>
          <Placeholder header="Вуз выбран">
            Теперь выберите группу — расписание появится на вкладке «Расписание».
          </Placeholder>
          <div style={{ padding: "0 16px 16px" }}>
            <Button size="l" stretched onClick={onPickGroup}>
              Выбрать группу
            </Button>
          </div>
        </Group>
      )}

      <Group>
        <div style={{ padding: "8px 16px 16px" }}>
          <Button size="l" mode="tertiary" stretched onClick={onReset}>
            Сбросить профиль
          </Button>
        </div>
      </Group>
    </Panel>
  );
}
