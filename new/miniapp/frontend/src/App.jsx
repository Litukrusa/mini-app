import { useCallback, useEffect, useState } from "react";
import {
  ConfigProvider,
  AppRoot,
  Tabbar,
  TabbarItem,
  FixedLayout,
  Spinner,
} from "@vkontakte/vkui";
import {
  Icon28CalendarOutline,
  Icon28UserCircleOutline,
} from "@vkontakte/icons";
import { initBridge } from "./bridge";
import {
  getMe,
  searchGroups,
  searchTeachers,
  searchAuditoriums,
  bindGroup,
  bindTeacher,
  bindAud,
  refreshGroups,
  refreshTeachers,
  refreshAuditoriums,
  eiosLogout,
} from "./api";
import { universitySearchConfig } from "./utils/university";
import { SchedulePanel } from "./panels/SchedulePanel";
import { ProfilePanel } from "./panels/ProfilePanel";
import { SettingsPanel } from "./panels/SettingsPanel";
import { EiosAuthPanel } from "./panels/EiosAuthPanel";
import { SearchPanel } from "./components/SearchPanel";

const PANEL = {
  schedule: "schedule",
  profile: "profile",
  settings: "settings",
  eiosAuth: "eios-auth",
  searchGroup: "search-group",
  searchTeacher: "search-teacher",
  searchAud: "search-aud",
};

function hideTabbar(panel) {
  return (
    panel === PANEL.searchGroup ||
    panel === PANEL.searchTeacher ||
    panel === PANEL.searchAud ||
    panel === PANEL.eiosAuth
  );
}

export default function App() {
  const [appearance, setAppearance] = useState("dark");
  const [booted, setBooted] = useState(false);
  const [me, setMe] = useState(null);
  const [tab, setTab] = useState("schedule");
  const [panel, setPanel] = useState(PANEL.schedule);
  const [snack, setSnack] = useState(null);

  const refreshMe = useCallback(async () => {
    const data = await getMe();
    setMe(data);
    return data;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { appearance: app } = await initBridge();
        if (!cancelled) setAppearance(app || "dark");
        const data = await getMe();
        if (!cancelled) {
          setMe(data);
          setPanel(PANEL.profile);
          setTab("profile");
        }
      } catch (e) {
        if (!cancelled) setSnack(e.message || "Ошибка загрузки");
      } finally {
        if (!cancelled) setBooted(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const goTab = (name) => {
    setTab(name);
    setPanel(name === "schedule" ? PANEL.schedule : PANEL.profile);
  };

  const goSchedule = () => goTab("schedule");

  const openSearch = (kind) => {
    if (!me?.university) {
      setPanel(PANEL.settings);
      setTab("profile");
      setSnack("Сначала выберите вуз в настройках");
      return;
    }
    if (kind === "teacher") setPanel(PANEL.searchTeacher);
    else if (kind === "aud") setPanel(PANEL.searchAud);
    else setPanel(PANEL.searchGroup);
  };

  const handleEiosLogout = async () => {
    if (!confirm("Отключить дополнительную авторизацию?")) return;
    try {
      const data = await eiosLogout();
      setMe(data);
      setSnack("Дополнительная авторизация отключена");
    } catch (e) {
      setSnack(e.message);
    }
  };

  const pickItem = async (kind, item) => {
    try {
      let profile;
      if (kind === "group") profile = await bindGroup(item.id, item.name);
      else if (kind === "teacher") profile = await bindTeacher(item.id, item.name);
      else profile = await bindAud(item.id, item.name);
      setMe(profile);
      goSchedule();
    } catch (e) {
      setSnack(e.message);
    }
  };

  if (!booted) {
    return (
      <ConfigProvider appearance={appearance} platform="ios">
        <AppRoot>
          <Spinner size="medium" style={{ margin: "40vh auto", display: "block" }} />
        </AppRoot>
      </ConfigProvider>
    );
  }

  const searchCfg = universitySearchConfig(me?.university);

  let content = null;
  if (panel === PANEL.schedule) {
    content = <SchedulePanel me={me} onGoProfile={() => goTab("profile")} key={me?.activeSelection?.id || me?.selections?.group?.id || "none"} />;
  } else if (panel === PANEL.profile) {
    content = (
      <ProfilePanel
        me={me}
        onRefresh={refreshMe}
        onOpenSearch={openSearch}
        onOpenSettings={() => setPanel(PANEL.settings)}
        onOpenEios={() => setPanel(PANEL.eiosAuth)}
        onEiosLogout={handleEiosLogout}
        onGoSchedule={goSchedule}
      />
    );
  } else if (panel === PANEL.settings) {
    content = (
      <SettingsPanel
        me={me}
        onBack={() => {
          setPanel(PANEL.profile);
          setTab("profile");
        }}
        onRefresh={refreshMe}
        onPickGroup={() => {
          setPanel(PANEL.profile);
          setTab("profile");
          openSearch("group");
        }}
        onOpenEios={() => setPanel(PANEL.eiosAuth)}
        onEiosLogout={handleEiosLogout}
      />
    );
  } else if (panel === PANEL.eiosAuth) {
    content = (
      <EiosAuthPanel
        onBack={() => {
          setPanel(PANEL.profile);
          setTab("profile");
        }}
        onDone={(profile) => {
          setMe(profile);
          setPanel(PANEL.profile);
          setTab("profile");
          setSnack("Дополнительная авторизация включена");
        }}
      />
    );
  } else if (panel === PANEL.searchGroup) {
    content = (
      <SearchPanel
        key={`g-${me?.university}`}
        title="Поиск группы"
        showListOnOpen={searchCfg.showListOnOpen}
        minQueryLength={searchCfg.minQueryLength}
        typeMoreHint={searchCfg.typeMoreHint}
        placeholder={searchCfg.groupPlaceholder}
        emptyListHint="python3 scripts/fetch_rasp_cache.py"
        onBack={() => setPanel(PANEL.profile)}
        onSearch={searchGroups}
        onPick={(item) => pickItem("group", item)}
        onRefresh={async () => {
          try {
            await refreshGroups();
            setSnack("Список групп обновлён");
          } catch (e) {
            setSnack(e.message);
          }
        }}
      />
    );
  } else if (panel === PANEL.searchTeacher) {
    content = (
      <SearchPanel
        key={`t-${me?.university}`}
        title="Поиск преподавателя"
        showListOnOpen={searchCfg.showListOnOpen}
        minQueryLength={searchCfg.minQueryLength}
        typeMoreHint={searchCfg.typeMoreHint}
        placeholder={searchCfg.teacherPlaceholder}
        emptyListHint={searchCfg.emptyTeacherHint}
        onBack={() => setPanel(PANEL.profile)}
        onSearch={searchTeachers}
        onPick={(item) => pickItem("teacher", item)}
        onRefresh={async () => {
          try {
            await refreshTeachers();
            setSnack("Список преподавателей обновлён");
          } catch (e) {
            setSnack(e.message);
          }
        }}
      />
    );
  } else if (panel === PANEL.searchAud) {
    content = (
      <SearchPanel
        key={`a-${me?.university}`}
        title="Поиск аудитории"
        showListOnOpen={searchCfg.showListOnOpen}
        minQueryLength={searchCfg.minQueryLength}
        typeMoreHint={searchCfg.typeMoreHint}
        placeholder={searchCfg.audPlaceholder}
        emptyListHint={searchCfg.emptyAudHint}
        onBack={() => setPanel(PANEL.profile)}
        onSearch={searchAuditoriums}
        onPick={(item) => pickItem("aud", item)}
        onRefresh={async () => {
          try {
            await refreshAuditoriums();
            setSnack("Список аудиторий обновлён");
          } catch (e) {
            setSnack(e.message);
          }
        }}
      />
    );
  }

  return (
    <ConfigProvider appearance={appearance} platform="ios">
      <AppRoot>
        {snack ? (
          <div
            style={{
              padding: "10px 16px",
              background: "var(--vkui--color_background_negative_tint)",
              color: "var(--vkui--color_text_negative)",
              fontSize: 14,
            }}
          >
            {snack}
          </div>
        ) : null}

        <div style={{ paddingBottom: hideTabbar(panel) ? 0 : 56 }}>{content}</div>

        {!hideTabbar(panel) && (
          <FixedLayout vertical="bottom">
            <Tabbar>
              <TabbarItem
                selected={tab === "schedule"}
                onClick={() => goTab("schedule")}
                text="Расписание"
              >
                <Icon28CalendarOutline />
              </TabbarItem>
              <TabbarItem
                selected={tab === "profile"}
                onClick={() => goTab("profile")}
                text="Профиль"
              >
                <Icon28UserCircleOutline />
              </TabbarItem>
            </Tabbar>
          </FixedLayout>
        )}
      </AppRoot>
    </ConfigProvider>
  );
}
