import React, { useEffect, useRef } from "react";
import { toast } from "sonner";

/**
 * PwaUpdater
 * ──────────
 * Registers /sw.js, polls for updates every 60s, and when a new SW takes over
 * shows a brief "Updating to latest" toast and reloads the page so installed
 * PWA users always get the freshest frontend without re-installing.
 *
 * The service worker is configured to skipWaiting() + clients.claim() and
 * post a SW_ACTIVATED message, so as soon as a new SW activates the page
 * receives it and reloads.
 */
export default function PwaUpdater() {
  const reloadingRef = useRef(false);

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    let updatePoll;
    // Capture whether a SW already controlled this page at boot. We only
    // auto-reload if a NEW SW takes over (i.e. update), not on first install.
    const hadControllerAtBoot = !!navigator.serviceWorker.controller;

    const reloadOnce = (reason) => {
      if (reloadingRef.current) return;
      reloadingRef.current = true;
      toast.success("New version installed — refreshing…", { duration: 2500 });
      setTimeout(() => {
        try { window.location.reload(); } catch (e) { /* ignore */ }
      }, 1500);
    };

    // Only reload when an UPDATE causes a controller change.
    const onControllerChange = () => {
      if (hadControllerAtBoot) reloadOnce("controllerchange");
    };
    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);

    // Listen for the SW's explicit "I'm activated" broadcast — only relevant
    // for updates, not first install.
    const onMessage = (event) => {
      if (event.data && event.data.type === "SW_ACTIVATED" && hadControllerAtBoot) {
        reloadOnce("sw_message");
      }
    };
    navigator.serviceWorker.addEventListener("message", onMessage);

    navigator.serviceWorker
      .register("/sw.js", { scope: "/" })
      .then((reg) => {
        // If a new SW is already waiting at boot, ask it to take over.
        if (reg.waiting && navigator.serviceWorker.controller) {
          reg.waiting.postMessage({ type: "SKIP_WAITING" });
        }

        // Whenever a new SW is found, wire its installed→activated transition.
        reg.addEventListener("updatefound", () => {
          const nw = reg.installing;
          if (!nw) return;
          nw.addEventListener("statechange", () => {
            if (nw.state === "installed" && navigator.serviceWorker.controller) {
              // New version is ready — tell it to skip waiting; the
              // controllerchange / SW_ACTIVATED handler above will trigger reload.
              try { nw.postMessage({ type: "SKIP_WAITING" }); } catch (e) { /* ignore */ }
            }
          });
        });

        // Poll for updates every 60s while the tab is open.
        updatePoll = setInterval(() => {
          if (document.visibilityState === "visible") {
            reg.update().catch(() => {});
          }
        }, 60_000);

        // Also check immediately when the tab regains focus.
        const onVisibility = () => {
          if (document.visibilityState === "visible") reg.update().catch(() => {});
        };
        document.addEventListener("visibilitychange", onVisibility);
      })
      .catch(() => {
        // SW registration failure isn't fatal — the app still works.
      });

    return () => {
      if (updatePoll) clearInterval(updatePoll);
      navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
      navigator.serviceWorker.removeEventListener("message", onMessage);
    };
  }, []);

  return null;
}
