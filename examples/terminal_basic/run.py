"""Basic terminal template example."""

from kida import Environment


def main():
    env = Environment(autoescape="terminal", terminal_color="basic")

    template = env.from_string("""{{ "Kida Terminal Mode" | bold | cyan }}
{{ hr(40) }}

{{ "Status" | underline }}
  {{ icons.check | green }} Server running    {{ "pass" | badge }}
  {{ icons.cross | red }} Database offline  {{ "fail" | badge }}
  {{ icons.warn | yellow }} Cache low         {{ "warn" | badge }}

{{ "Progress" | underline }}
  Build:   {{ 0.85 | bar(width=25) }}
  Deploy:  {{ 0.45 | bar(width=25) }}
  Tests:   {{ 1.0 | bar(width=25) }}

{{ "System Info" | underline }}
{{ "Version" | kv("2.4.1", width=35) }}
{{ "Uptime" | kv("3h 42m", width=35) }}
{{ "Memory" | kv("1.2 GiB", width=35) }}
{{ "Workers" | kv("8/16", width=35) }}

{{ hr(40, title="Box Drawing") }}

{% let b = box.round %}{% let w = 40 -%}
{{ b.tl }}{{ b.h * (w - 2) }}{{ b.tr }}
{{ b.v }} {{ "Hello, Terminal!" | bold | pad(w - 4) }} {{ b.v }}
{{ b.bl }}{{ b.h * (w - 2) }}{{ b.br }}
""")

    print(template.render())


if __name__ == "__main__":
    main()
