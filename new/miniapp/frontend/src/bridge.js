import bridge from "@vkontakte/vk-bridge";
import { setLaunchParams } from "./api";

function isLocalDev() {
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1";
}

export async function initBridge() {
  if (isLocalDev()) {
    setLaunchParams("vk_user_id=1");
    return { appearance: "dark" };
  }

  await bridge.send("VKWebAppInit");

  const fromUrl =
    window.location.search.replace(/^\?/, "") ||
    window.location.hash.replace(/^#/, "");
  if (fromUrl) {
    setLaunchParams(fromUrl);
  } else {
    try {
      const data = await bridge.send("VKWebAppGetLaunchParams");
      setLaunchParams(
        Object.keys(data)
          .map((k) => `${k}=${data[k]}`)
          .join("&")
      );
    } catch {
      setLaunchParams("");
    }
  }

  let appearance = "light";
  try {
    const cfg = await bridge.send("VKWebAppGetConfig");
    const scheme = cfg?.scheme || cfg?.appearance;
    if (scheme === "space_gray" || scheme === "vkcom_dark" || scheme === "dark") {
      appearance = "dark";
    }
  } catch {
    if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
      appearance = "dark";
    }
  }

  return { appearance };
}

export { bridge };
