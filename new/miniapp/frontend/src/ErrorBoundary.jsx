import { Component } from "react";
import { ConfigProvider, AppRoot, Placeholder, Button } from "@vkontakte/vkui";

export class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <ConfigProvider appearance="dark" platform="ios">
          <AppRoot>
            <Placeholder
              header="Ошибка загрузки"
              action={
                <Button size="l" onClick={() => window.location.reload()}>
                  Обновить
                </Button>
              }
            >
              {this.state.error.message || String(this.state.error)}
            </Placeholder>
          </AppRoot>
        </ConfigProvider>
      );
    }
    return this.props.children;
  }
}
