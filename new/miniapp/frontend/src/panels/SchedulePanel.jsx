import { useCallback, useEffect, useState } from "react";
import {
  Panel,
  PanelHeader,
  Group,
  Placeholder,
  Header,
  SimpleCell,
  Spinner,
  Button,
  ButtonGroup,
} from "@vkontakte/vkui";
import { Icon56GhostOutline } from "@vkontakte/icons";
import { getSchedule } from "../api";
import { WeekStrip } from "../components/WeekStrip";
import { todayIso, parseIso, weekDays } from "../utils/dates";
import { getActiveSelection } from "../utils/profile";

export function SchedulePanel({ me, onGoProfile }) {
  const [selectedDate, setSelectedDate] = useState(todayIso());
  const [lessons, setLessons] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const selection = getActiveSelection(me);
  const hasSelection = Boolean(selection?.id);
  const dayMeta = weekDays(parseIso(selectedDate)).find((d) => d.iso === selectedDate);

  const load = useCallback(async () => {
    if (!hasSelection) return;
    setLoading(true);
    setError("");
    try {
      const data = await getSchedule({ date: selectedDate });
      setLessons(data.lessons || []);
    } catch (e) {
      setError(e.message || "Ошибка загрузки");
      setLessons([]);
    } finally {
      setLoading(false);
    }
  }, [selectedDate, hasSelection, selection?.id, selection?.kind]);

  useEffect(() => {
    load();
  }, [load]);

  const headerTitle = selection?.name
    ? `Расписание · ${selection.name}`
    : "Расписание";

  return (
    <Panel id="schedule">
      <PanelHeader>{headerTitle}</PanelHeader>

      {!hasSelection ? (
        <Group>
          <Placeholder
            icon={<Icon56GhostOutline />}
            action={
              <Button size="l" stretched onClick={onGoProfile}>
                Выбрать группу в профиле
              </Button>
            }
          >
            Сначала выберите группу, преподавателя или аудиторию на вкладке «Профиль»
          </Placeholder>
        </Group>
      ) : (
        <>
          <Group>
            <div style={{ padding: "8px 12px 0" }}>
              <ButtonGroup mode="segmented" stretched>
                <Button
                  size="m"
                  mode={selectedDate === todayIso() ? "primary" : "secondary"}
                  onClick={() => setSelectedDate(todayIso())}
                >
                  Сегодня
                </Button>
                <Button
                  size="m"
                  mode="secondary"
                  onClick={() => {
                    const t = parseIso(todayIso());
                    t.setDate(t.getDate() + 1);
                    const y = t.getFullYear();
                    const m = String(t.getMonth() + 1).padStart(2, "0");
                    const d = String(t.getDate()).padStart(2, "0");
                    setSelectedDate(`${y}-${m}-${d}`);
                  }}
                >
                  Завтра
                </Button>
              </ButtonGroup>
            </div>
            <WeekStrip selectedDate={selectedDate} onSelect={setSelectedDate} />
          </Group>

          <Group>
            <Header mode="primary">
              {dayMeta?.full || "День"}
              {selection?.name ? ` · ${selection.name}` : ""}
            </Header>
            {loading && <Spinner size="medium" style={{ margin: 16 }} />}
            {!loading && error && (
              <Placeholder
                header="Не удалось загрузить"
                action={
                  <Button size="m" onClick={load}>
                    Повторить
                  </Button>
                }
              >
                {error}
                {me?.university === "D" && !me?.eiosAuthenticated ? (
                  <>
                    <br />
                    <br />
                    Для части групп ДГТУ нужна доп. авторизация ЭИОС (вкладка «Профиль»).
                  </>
                ) : null}
              </Placeholder>
            )}
            {!loading && !error && lessons.length === 0 && (
              <Placeholder icon={<Icon56GhostOutline />}>
                На этот день пар нет
                {me?.university === "D" && !me?.eiosAuthenticated ? (
                  <>
                    <br />
                    <br />
                    Если пары должны быть — включите доп. авторизацию ЭИОС в профиле.
                  </>
                ) : null}
              </Placeholder>
            )}
            {!loading &&
              !error &&
              lessons.map((l, idx) => (
                <SimpleCell
                  key={`${l.date}-${l.start}-${idx}`}
                  subtitle={`${l.teacher || l.group || ""}${l.auditorium ? ` · ${l.auditorium}` : ""} · ${l.start}${l.end ? `–${l.end}` : ""}`}
                  multiline
                >
                  {l.typeEmoji} {l.discipline}
                </SimpleCell>
              ))}
          </Group>
        </>
      )}
    </Panel>
  );
}
