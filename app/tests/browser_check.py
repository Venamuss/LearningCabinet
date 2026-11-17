"""Run with `python -m app.tests.browser_check` in a Playwright environment."""

import argparse
import json
from socketserver import ThreadingMixIn
from threading import Thread
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from app import preview

preview.configure()

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.wsgi import get_wsgi_application
from playwright.sync_api import sync_playwright


class Server(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=("chromium", "firefox"))
    parser.add_argument("--width", type=int, choices=(1440, 1280, 768, 360))
    options = parser.parse_args()
    output = preview.ROOT / "var" / "ui-checks"
    output.mkdir(parents=True, exist_ok=True)
    server = make_server(
        "127.0.0.1",
        0,
        StaticFilesHandler(get_wsgi_application()),
        server_class=Server,
        handler_class=QuietHandler,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    report = {"browsers": {}, "screens": [], "interactions": []}
    try:
        with sync_playwright() as playwright:
            for engine in (
                [options.browser] if options.browser else ("chromium", "firefox")
            ):
                browser = getattr(playwright, engine).launch()
                report["browsers"][engine] = browser.version
                page = browser.new_page(
                    viewport={"width": 1440, "height": 960},
                    locale="ru-RU",
                    color_scheme="light",
                )
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                for width in (
                    [options.width] if options.width else (1440, 1280, 768, 360)
                ):
                    page.set_viewport_size({"width": width, "height": 960})
                    for screen in preview.SCREENS:
                        response = page.goto(
                            f"{base}/preview/{screen}/", wait_until="load"
                        )
                        assert response.status == 200, (screen, response.status)
                        page.evaluate("document.fonts.ready")
                        geometry = page.evaluate("""() => ({
                            width: document.documentElement.clientWidth,
                            scroll: document.documentElement.scrollWidth,
                            font: document.fonts.check('14px Inter', 'Учебный кабинет'),
                            background: getComputedStyle(document.body).backgroundColor,
                            overflow: [...document.querySelectorAll('body *')].filter(e => {
                                const r = e.getBoundingClientRect();
                                return r.width && r.right > innerWidth + 1 && getComputedStyle(e).position !== 'absolute';
                            }).map(e => e.tagName + '.' + e.className)
                        })""")
                        assert geometry["scroll"] <= geometry["width"], (
                            engine,
                            width,
                            screen,
                            geometry,
                        )
                        assert geometry["font"], (engine, screen, "Inter not loaded")
                        assert geometry["background"] == "rgb(245, 246, 243)", geometry
                        assert not errors, (screen, errors)
                        page.screenshot(
                            path=str(output / f"{engine}-{width}-{screen}.png"),
                            full_page=True,
                        )
                        report["screens"].append(
                            {
                                "browser": engine,
                                "width": width,
                                "screen": screen,
                                "horizontal_overflow": False,
                            }
                        )
                    print(f"{engine}: {width}px, all 27 frames passed", flush=True)

                page.set_viewport_size({"width": 360, "height": 960})
                page.goto(f"{base}/preview/media_file/")
                page.locator(".mobile-only button").click()
                page.wait_for_url("**/logout/")
                assert "Данные не изменены." in page.locator("body").inner_text()
                report["interactions"].append(
                    f"{engine}: CSRF-safe logout from media page"
                )

                page.goto(f"{base}/preview/admin_users/")
                page.locator("[data-menu-toggle]").click()
                assert page.locator(".app-sidebar").is_visible()
                assert (
                    page.locator("[data-menu-toggle]").get_attribute("aria-expanded")
                    == "true"
                )
                page.locator("[data-menu-toggle]").click()
                assert not page.locator(".app-sidebar").is_visible()
                report["interactions"].append(f"{engine}: mobile menu")

                page.goto(f"{base}/preview/material_file/")
                assert page.locator('[data-source-panel="file"]').is_visible()
                page.locator("[data-source-switch] label").filter(
                    has_text="Ссылка"
                ).click()
                assert page.locator('[data-source-panel="link"]').is_visible()
                assert page.locator('[name="file"]').is_disabled()
                page.locator('[name="external_url"]').fill(
                    "https://example.org/test.webm"
                )
                page.locator("[data-source-switch] label").filter(
                    has_text="Файл"
                ).click()
                assert page.locator('[name="external_url"]').is_disabled()
                page.locator("[data-source-switch] label").filter(
                    has_text="Ссылка"
                ).click()
                assert (
                    page.locator('[name="external_url"]').input_value()
                    == "https://example.org/test.webm"
                )
                report["interactions"].append(
                    f"{engine}: material source switching preserves input"
                )

                page.goto(f"{base}/preview/admin_user/")
                page.locator('[name="role"]').select_option("teacher")
                assert not page.locator("[data-student-group]").is_visible()
                assert page.locator('[name="study_group"]').is_disabled()
                page.locator('[name="role"]').select_option("student")
                assert page.locator('[name="study_group"]').is_enabled()
                assert (
                    page.locator('[name="study_group"]').get_attribute("required")
                    is not None
                )
                report["interactions"].append(f"{engine}: user role/group")

                page.goto(f"{base}/preview/admin_lesson/")
                page.locator('[name="action"]').select_option("cancel")
                assert not page.locator('[name="start_time"]').is_visible()
                assert page.locator('[name="start_time"]').is_disabled()
                page.locator('[name="action"]').select_option("extra")
                assert not page.locator("[data-template-field]").is_visible()
                assert page.locator('[name="start_time"]').is_visible()
                report["interactions"].append(
                    f"{engine}: extra/replacement/cancellation"
                )

                page.goto(f"{base}/preview/material_delete/")
                assert page.evaluate(
                    'document.querySelector("dialog").matches(":modal")'
                )
                assert page.locator("dialog a").evaluate(
                    "(e) => e === document.activeElement"
                )
                page.keyboard.press("Shift+Tab")
                assert page.locator("dialog button").evaluate(
                    "(e) => e === document.activeElement"
                )
                page.keyboard.press("Escape")
                page.wait_for_url("**/teacher/materials/")
                report["interactions"].append(
                    f"{engine}: confirmation focus trap and Escape"
                )

                for screen, tag in (("media_file", "video"), ("media_link", "audio")):
                    page.goto(f"{base}/preview/{screen}/")
                    page.wait_for_function(
                        f'document.querySelector("{tag}").readyState >= 2'
                    )
                    page.locator(tag).evaluate("(media) => media.play()")
                    page.wait_for_function(
                        f'document.querySelector("{tag}").currentTime > 0'
                    )
                    page.locator(tag).evaluate(
                        "(media) => { media.pause(); media.currentTime = Math.min(1, media.duration / 2); media.volume = 0.5; }"
                    )
                    assert page.locator(tag).evaluate(
                        "(media) => media.paused && media.volume === 0.5"
                    )
                    page.locator(tag).evaluate(
                        '(media) => { media.src = "/preview-assets/missing.webm"; media.load(); }'
                    )
                    page.locator("[data-media-error]").wait_for(state="visible")
                    report["interactions"].append(
                        f"{engine}: {tag} playback/pause/seek/volume/error"
                    )

                page.goto(f"{base}/preview/admin_users/")
                page.locator(".user-status").first.click()
                page.wait_for_url("**/manage/users/1/block/")
                assert "Данные не изменены." in page.locator("body").inner_text()
                assert not errors, errors
                report["interactions"].append(
                    f"{engine}: mutation explicitly unavailable"
                )
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        suffix = (
            f'-{options.browser or "all"}-{options.width or "all"}'
            if options.browser or options.width
            else ""
        )
        (output / f"report{suffix}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
    print(
        f"Passed: {len(report['screens'])} responsive renders and {len(report['interactions'])} interaction checks."
    )
    print(json.dumps(report["browsers"], ensure_ascii=False))
    print(f"Screenshots and report: {output}")


if __name__ == "__main__":
    main()
