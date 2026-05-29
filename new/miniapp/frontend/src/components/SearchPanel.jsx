import { useCallback, useEffect, useState } from "react";
import {
  Panel,
  PanelHeader,
  PanelHeaderBack,
  Group,
  Search,
  SimpleCell,
  Spinner,
  Button,
  Placeholder,
} from "@vkontakte/vkui";

export function SearchPanel({
  title,
  placeholder,
  onBack,
  onSearch,
  onPick,
  showListOnOpen = false,
  minQueryLength = 0,
  typeMoreHint = null,
  emptyListHint = null,
  onRefresh,
}) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  const runSearch = useCallback(
    async (q) => {
      setLoading(true);
      try {
        const data = await onSearch(q);
        setItems(data || []);
      } catch {
        setItems([]);
      } finally {
        setLoading(false);
      }
    },
    [onSearch]
  );

  const qTrim = query.trim();
  const qTooShort = qTrim.length > 0 && qTrim.length < minQueryLength;

  useEffect(() => {
    if (showListOnOpen && !qTrim) {
      runSearch("");
      return;
    }
    if (!qTrim) {
      setItems([]);
      return;
    }
    if (qTooShort) {
      setItems([]);
      return;
    }
    const t = setTimeout(() => runSearch(qTrim), 300);
    return () => clearTimeout(t);
  }, [query, showListOnOpen, runSearch, qTrim, qTooShort]);

  return (
    <Panel id="search">
      <PanelHeader before={<PanelHeaderBack onClick={onBack} />}>
        {title}
      </PanelHeader>
      <Group>
        <Search
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder || "Поиск"}
        />
        {onRefresh && (
          <div style={{ padding: "8px 12px 0" }}>
            <Button size="s" mode="secondary" stretched onClick={onRefresh}>
              Обновить список с сервера
            </Button>
          </div>
        )}
      </Group>
      <Group>
        {loading && <Spinner size="medium" style={{ margin: 24 }} />}
        {!loading && qTooShort && typeMoreHint && (
          <Placeholder>{typeMoreHint}</Placeholder>
        )}
        {!loading && !items.length && !qTrim && showListOnOpen && (
          <Placeholder header="Список пуст">{emptyListHint}</Placeholder>
        )}
        {!loading && !items.length && qTrim && !qTooShort && (
          <SimpleCell disabled>Ничего не найдено</SimpleCell>
        )}
        {!loading &&
          items.map((item) => (
            <SimpleCell
              key={item.id}
              onClick={() => onPick(item)}
              subtitle={item.subtitle || null}
            >
              {item.name}
            </SimpleCell>
          ))}
      </Group>
    </Panel>
  );
}
