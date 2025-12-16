from __future__ import annotations

import argparse
import time

from .logging_utils import enable_console_logging


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recaptcha-domain-replicator",
        description="Serve a local replica of a ReCAPTCHA widget and capture the token.",
    )
    parser.add_argument(
        "--log-level",
        default="OFF",
        type=str.upper,
        choices=["OFF", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Enable console logs at this level. Default: OFF (no logs).",
    )

    # Add commands to the parser
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "demo",
        help="Run a simple demo using the Google test sitekey.",
    )

    # Add the replicate command to the parser
    replicate = subparsers.add_parser(
        "replicate",
        help="Replicate a reCAPTCHA widget for a given sitekey and URL.",
    )
    replicate.add_argument("--website-key", required=True, help="The reCAPTCHA site key.")
    replicate.add_argument(
        "--website-url", required=True, help="The page URL the key is registered for."
    )
    replicate.add_argument(
        "--download-dir",
        default="tmp",
        help="Directory to write the generated HTML when --persist-html is enabled.",
    )
    replicate.add_argument(
        "--persist-html",
        action="store_true",
        help="Persist the generated HTML file to disk (default: disabled; served from memory).",
    )
    replicate.add_argument(
        "--server-port",
        type=int,
        default=8080,
        help="Preferred port to bind (a free port will be chosen if it's in use).",
    )
    replicate.add_argument(
        "--proxy",
        default=None,
        help="Optional proxy URL (e.g., http://user:pass@host:port).",
    )
    replicate.add_argument(
        "--browser-path",
        default=None,
        help="Optional path to the Chrome/Edge executable to launch.",
    )
    replicate.add_argument(
        "--observation-time",
        type=int,
        default=120,
        help="Seconds to keep the browser open (0 = until solved/closed).",
    )
    replicate.add_argument("--invisible", action="store_true", help="Use invisible reCAPTCHA.")
    replicate.add_argument(
        "--enterprise", action="store_true", help="Use enterprise reCAPTCHA API."
    )
    replicate.add_argument(
        "--api-domain", default="google.com", help="API domain (default: google.com)."
    )
    replicate.add_argument(
        "--data-s", dest="data_s_value", default=None, help="Optional data-s value."
    )
    replicate.add_argument(
        "--action", default=None, help="Optional action parameter for invisible reCAPTCHA."
    )
    replicate.add_argument(
        "--bypass-domain-check",
        action="store_true",  # Store True if the argument is present
        help=(
            "Attempt domain spoofing (hosts file / host-resolver-rules) to bypass key restrictions."
        ),
    )
    replicate.add_argument(
        "--no-ssl",
        dest="use_ssl",
        action="store_false",  # Store False if the argument is present
        help="Serve over HTTP instead of HTTPS.",
    )
    replicate.set_defaults(use_ssl=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.log_level != "OFF":
        enable_console_logging(args.log_level)

    # If no command is provided, print the help
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "demo":
            from .demo import run_demo

            run_demo()
            return 0

        if args.command == "replicate":
            from .captcha_replicator import RecaptchaDomainReplicator

            try:
                replicator = RecaptchaDomainReplicator(
                    download_dir=args.download_dir,
                    server_port=args.server_port,
                    persist_html=args.persist_html,
                    proxy=args.proxy,
                    browser_path=args.browser_path,
                )
            except ValueError as exc:
                print(f"Invalid proxy: {exc}")
                return 2
            try:
                browser, token_handle = replicator.replicate_captcha(
                    website_key=args.website_key,
                    website_url=args.website_url,
                    is_invisible=args.invisible,
                    data_s_value=args.data_s_value,
                    is_enterprise=args.enterprise,
                    api_domain=args.api_domain,
                    observation_time=args.observation_time,
                    bypass_domain_check=args.bypass_domain_check,
                    use_ssl=args.use_ssl,
                    action=args.action,
                )

                if not browser:
                    print("Failed to start reCAPTCHA session. See error messages above.")
                    return 2

                # observation_time > 0: wait up to N seconds
                # observation_time == 0: wait until token is captured or browser is closed
                deadline = (
                    None
                    if args.observation_time == 0
                    else (time.time() + max(0, args.observation_time))
                )
                poll_sleep = 0.2 if args.invisible else 1.0

                token = None
                while True:
                    token = token_handle.get() if token_handle else None
                    if token:
                        break

                    try:
                        _ = replicator.tab.url
                    except Exception:
                        break

                    if deadline is not None and time.time() >= deadline:
                        break

                    if token_handle is not None:
                        remaining = None if deadline is None else max(0.0, deadline - time.time())
                        token_handle.wait(
                            timeout=poll_sleep if remaining is None else min(poll_sleep, remaining)
                        )
                    else:
                        remaining = None if deadline is None else max(0.0, deadline - time.time())
                        time.sleep(poll_sleep if remaining is None else min(poll_sleep, remaining))

                if token:
                    print(token)
                    return 0

                print("No token obtained.")
                return 2
            finally:
                replicator.close_browser()
                replicator.stop_http_server()

        parser.print_help()
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
