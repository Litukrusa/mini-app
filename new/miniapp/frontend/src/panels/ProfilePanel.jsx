import {
  Panel,
  PanelHeader,
  Group,
  Header,
  Placeholder,
  Button,
  SimpleCell,
  SegmentedControl,
} from "@vkontakte/vkui";
import {
  Icon56UsersOutline,
  Icon56UserCircleOutline,
  Icon56DoorArrowRightOutline,
  Icon28SettingsOutline,
} from "@vkontakte/icons";
import { setScheduleKind } from "../api";
import { EiosAuthButton } from "../components/EiosAuthButton";
import { getActiveSelection } from "../utils/profile";

const KINDS = [
  { label: "Группа", value: "group" },
  { label: "Преподаватель", value: "teacher" },
  { label: "Аудитория", value: "aud" },
];

const EMPTY = {
  group: {
    icon: <Icon56UsersOutline />,
    text: "Выберите учебную группу, расписание которой хотите посмотреть",
    btn: "Выбрать группу",
  },
  teacher: {
    icon: <Icon56UserCircleOutline />,
    text: "Выберите преподавателя, расписание которого хотите посмотреть",
    btn: "Выбрать преподавателя",
  },
  aud: {
    icon: <Icon56DoorArrowRightOutline />,
    text: "Выберите аудиторию, расписание которой хотите посмотреть",
    btn: "Выбрать аудиторию",
  },
};

export function ProfilePanel({
  me,
  onRefresh,
  onOpenSearch,
  onOpenSettings,
  onOpenEios,
  onEiosLogout,
  onGoSchedule,
}) {
  const kind = me?.scheduleKind || "group";
  const selection = getActiveSelection(me) || me?.selections?.[kind];
  const empty = EMPTY[kind] || EMPTY.group;
  const hasUniversity = Boolean(me?.university);

  const onKindChange = async (value) => {
    if (!value || value === kind) return;
    await setScheduleKind(value);
    onRefresh();
  };

  return (
    <Panel id="profile">
      <PanelHeader>Профиль</PanelHeader>

      {!hasUniversity && (
        <Group>
          <Placeholder
            header="Шаг 1"
            action={
              <Button size="l" stretched onClick={onOpenSettings}>
                Выбрать вуз
              </Button>
            }
          >
            Сначала укажите ПИ ДГТУ или ДГТУ в настройках
          </Placeholder>
        </Group>
      )}

      <Group>
        <Header mode="secondary">Расписание по</Header>
        <div style={{ padding: "0 12px 4px" }}>
          <SegmentedControl
            size="l"
            name="schedule-kind"
            value={kind}
            onChange={onKindChange}
            options={KINDS}
          />
        </div>
        <EiosAuthButton me={me} onConnect={onOpenEios} onDisconnect={onEiosLogout} />
      </Group>

      <Group>
        {!hasUniversity ? (
          <Placeholder>После выбора вуза здесь появится кнопка выбора группы</Placeholder>
        ) : selection?.name ? (
          <>
            <SimpleCell subtitle="Текущий выбор"> {selection.name} </SimpleCell>
            <div style={{ padding: "0 16px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
              <Button size="l" mode="primary" stretched onClick={onGoSchedule}>
                Открыть расписание
              </Button>
              <Button size="l" mode="secondary" stretched onClick={() => onOpenSearch(kind)}>
                Изменить
              </Button>
            </div>
          </>
        ) : (
          <Placeholder
            icon={empty.icon}
            action={
              <Button size="l" stretched onClick={() => onOpenSearch(kind)}>
                {empty.btn}
              </Button>
            }
          >
            {empty.text}
          </Placeholder>
        )}
      </Group>

      <Group>
        <SimpleCell before={<Icon28SettingsOutline />} onClick={onOpenSettings}>
          Настройки
        </SimpleCell>
      </Group>
    </Panel>
  );
}
