"""Typer CLI entry point for the social media automation agent."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from social_agent.config import get_settings, ensure_output_dirs
from social_agent.models.content import Platform
from social_agent.profiles.loader import load_profile

app = typer.Typer(
    name="social-agent",
    help="AI-powered social media content automation agent.",
    no_args_is_help=True,
)
console = Console()

# Sub-command groups
schedule_app = typer.Typer(help="Manage scheduled posts.")
research_app = typer.Typer(help="Viral content research and niche intelligence.")
replies_app = typer.Typer(help="Manage comment replies and engagement.")
analytics_app = typer.Typer(help="Content performance analytics.")
calendar_app = typer.Typer(help="Content calendar management.")

auth_app = typer.Typer(help="OpenAI OAuth authentication.")

app.add_typer(schedule_app, name="schedule")
app.add_typer(research_app, name="research")
app.add_typer(replies_app, name="replies")
app.add_typer(analytics_app, name="analytics")
app.add_typer(calendar_app, name="calendar")
app.add_typer(auth_app, name="auth")


# --- Tweet ---


@app.command()
def tweet(
    topic: str = typer.Argument(..., help="Topic for the tweet"),
    style: str = typer.Option("engaging", help="Style: engaging, educational, controversial"),
    thread: bool = typer.Option(False, "--thread", help="Generate a thread instead of single tweet"),
    num_tweets: int = typer.Option(5, "--num-tweets", help="Number of tweets in thread"),
    variants: int = typer.Option(1, "--variants", help="Number of A/B variants to generate"),
    post: bool = typer.Option(False, "--post", help="Post immediately after generation"),
    profile_path: str = typer.Option(None, "--profile", help="Path to influencer profile"),
) -> None:
    """Generate a tweet or thread in the influencer's voice."""
    profile = load_profile(profile_path)

    if thread:
        from social_agent.generators.tweet import generate_thread

        for i in range(variants):
            result = generate_thread(topic, profile, num_tweets)
            label = f" (Variant {i + 1})" if variants > 1 else ""
            console.print(Panel(result.text, title=f"Thread Hook{label}", border_style="cyan"))
            for j, t in enumerate(result.thread_tweets, 1):
                console.print(f"  [dim]{j}.[/dim] {t}")
            if result.hashtags:
                console.print(f"  [green]#{' #'.join(result.hashtags)}[/green]")
            console.print()
    else:
        from social_agent.generators.tweet import generate_tweet

        for i in range(variants):
            result = generate_tweet(topic, profile, style)
            label = f" (Variant {i + 1})" if variants > 1 else ""
            console.print(Panel(result.text, title=f"Tweet{label}", border_style="cyan"))
            if result.hashtags:
                console.print(f"  [green]#{' #'.join(result.hashtags)}[/green]")
            console.print()


# --- Carousel ---


@app.command()
def carousel(
    topic: str = typer.Argument(..., help="Topic for the carousel"),
    platform: str = typer.Option("ig", "--platform", help="Platform: ig, tiktok, twitter"),
    num_slides: int = typer.Option(7, "--slides", help="Number of slides"),
    render: bool = typer.Option(True, "--render/--no-render", help="Render slides as images"),
    profile_path: str = typer.Option(None, "--profile", help="Path to influencer profile"),
) -> None:
    """Generate carousel slide content and render branded images."""
    profile = load_profile(profile_path)

    platform_map = {"ig": Platform.INSTAGRAM, "tiktok": Platform.TIKTOK, "twitter": Platform.TWITTER}
    plat = platform_map.get(platform, Platform.INSTAGRAM)

    from social_agent.generators.carousel import generate_carousel

    result = generate_carousel(topic, profile, num_slides, plat)

    console.print(Panel(result.title, title="Carousel", border_style="magenta"))
    for i, slide in enumerate(result.slides, 1):
        console.print(f"  [bold]Slide {i}:[/bold] {slide.heading}")
        console.print(f"    {slide.body}")
    if result.caption:
        console.print(f"\n[dim]Caption:[/dim] {result.caption}")
    if result.hashtags:
        console.print(f"[green]#{' #'.join(result.hashtags)}[/green]")

    if render:
        from social_agent.renderers.carousel_renderer import render_carousel as render_imgs

        ensure_output_dirs()
        paths = render_imgs(result, profile.brand)
        console.print(f"\n[green]✓[/green] Rendered {len(paths)} slides:")
        for p in paths:
            console.print(f"  {p}")


# --- TikTok ---


@app.command()
def tiktok(
    topic: str = typer.Argument(..., help="Topic for the TikTok"),
    style: str = typer.Option("educational", help="Style: educational, storytelling, tutorial"),
    profile_path: str = typer.Option(None, "--profile", help="Path to influencer profile"),
) -> None:
    """Generate a TikTok caption and script notes."""
    profile = load_profile(profile_path)

    from social_agent.generators.tiktok import generate_tiktok_caption

    result = generate_tiktok_caption(topic, profile, style)

    console.print(Panel(result.caption, title="TikTok Caption", border_style="red"))
    if result.hashtags:
        console.print(f"[green]#{' #'.join(result.hashtags)}[/green]")
    if result.sound_suggestion:
        console.print(f"[dim]Suggested sound:[/dim] {result.sound_suggestion}")
    if result.script_notes:
        console.print(Panel(result.script_notes, title="Script Notes", border_style="yellow"))


# --- Create (all platforms) ---


@app.command()
def create(
    topic: str = typer.Argument(..., help="Content topic"),
    all_platforms: bool = typer.Option(False, "--all-platforms", help="Generate for all platforms"),
    profile_path: str = typer.Option(None, "--profile", help="Path to influencer profile"),
) -> None:
    """Generate content for all platforms from a single topic."""
    profile = load_profile(profile_path)

    if all_platforms:
        from social_agent.generators.repurposer import repurpose_content

        results = repurpose_content(topic, profile)
        for platform_name, content in results.items():
            console.print(Panel(str(content), title=platform_name.upper(), border_style="blue"))
    else:
        console.print("[yellow]Use --all-platforms to generate for all platforms, or use tweet/carousel/tiktok commands.[/yellow]")


# --- Schedule ---


@schedule_app.command("list")
def schedule_list() -> None:
    """View pending scheduled posts."""
    console.print("[dim]No scheduled posts. Use --schedule flag when generating content.[/dim]")


@schedule_app.command("approve")
def schedule_approve(post_id: int = typer.Argument(..., help="Post ID to approve")) -> None:
    """Approve a pending post for publishing."""
    console.print(f"[green]✓[/green] Post {post_id} approved.")


# --- Research ---


@research_app.command("scan")
def research_scan(
    profile_path: str = typer.Option(None, "--profile", help="Path to influencer profile"),
) -> None:
    """Scan niche for viral content."""
    profile = load_profile(profile_path)
    console.print("[cyan]Scanning niche for viral content...[/cyan]")

    from social_agent.research.scraper import scan_niche

    results = scan_niche(profile)
    console.print(f"[green]✓[/green] Found {len(results)} viral posts.")
    for post in results[:5]:
        console.print(f"  [{post.platform.value}] {post.text[:100]}... ({post.likes} likes)")


@research_app.command("trends")
def research_trends(
    profile_path: str = typer.Option(None, "--profile", help="Path to influencer profile"),
) -> None:
    """Show current trending topics and hooks."""
    console.print("[cyan]Analyzing niche trends...[/cyan]")

    from social_agent.research.analyzer import get_latest_intelligence

    intel = get_latest_intelligence()
    if intel:
        console.print(Panel(
            "\n".join(f"• {t}" for t in intel.trending_topics),
            title="Trending Topics",
            border_style="green",
        ))
        if intel.winning_hooks:
            console.print(Panel(
                "\n".join(f"• {h.pattern}" for h in intel.winning_hooks[:5]),
                title="Winning Hooks",
                border_style="yellow",
            ))
    else:
        console.print("[dim]No trend data yet. Run 'social-agent research scan' first.[/dim]")


@research_app.command("competitors")
def research_competitors(
    profile_path: str = typer.Option(None, "--profile", help="Path to influencer profile"),
) -> None:
    """Show competitor analysis."""
    profile = load_profile(profile_path)
    console.print("[cyan]Analyzing competitors...[/cyan]")

    from social_agent.research.competitors import analyze_competitors

    report = analyze_competitors(profile)
    for comp in report:
        console.print(f"  [@{comp.handle}] Avg likes: {comp.avg_likes:.0f}, Topics: {', '.join(comp.top_topics[:3])}")


@research_app.command("swipe-file")
def research_swipe_file() -> None:
    """Browse saved viral content examples."""
    console.print("[dim]Swipe file is empty. Run 'social-agent research scan' to populate.[/dim]")


# --- Replies ---


@replies_app.command("fetch")
def replies_fetch(
    profile_path: str = typer.Option(None, "--profile", help="Path to influencer profile"),
) -> None:
    """Fetch latest comments and mentions."""
    console.print("[cyan]Fetching comments and mentions...[/cyan]")
    console.print("[dim]No new comments found.[/dim]")


@replies_app.command("draft")
def replies_draft() -> None:
    """Generate reply drafts for pending comments."""
    console.print("[dim]No comments to draft replies for. Run 'social-agent replies fetch' first.[/dim]")


@replies_app.command("approve")
def replies_approve(reply_id: int = typer.Argument(..., help="Reply ID to approve")) -> None:
    """Approve a reply draft for posting."""
    console.print(f"[green]✓[/green] Reply {reply_id} approved.")


# --- Analytics ---


@analytics_app.command("report")
def analytics_report(
    last: str = typer.Option("7d", "--last", help="Time period: 7d, 30d, etc."),
) -> None:
    """Generate a performance report."""
    console.print(f"[cyan]Generating analytics report for last {last}...[/cyan]")
    console.print("[dim]No analytics data yet. Post content first, then check back.[/dim]")


@analytics_app.command("top-posts")
def analytics_top_posts() -> None:
    """Show best performing content."""
    console.print("[dim]No published posts to analyze yet.[/dim]")


# --- Calendar ---


@calendar_app.command("generate")
def calendar_generate(
    week: bool = typer.Option(False, "--week", help="Generate for the upcoming week"),
    days: int = typer.Option(7, "--days", help="Number of days to plan"),
    topics: str = typer.Option(None, "--topics", help="Comma-separated topic list"),
    profile_path: str = typer.Option(None, "--profile", help="Path to influencer profile"),
) -> None:
    """Generate a content calendar."""
    profile = load_profile(profile_path)
    topic_list = [t.strip() for t in topics.split(",")] if topics else None

    console.print(f"[cyan]Generating {days}-day content calendar...[/cyan]")

    from social_agent.calendar.planner import generate_calendar

    calendar = generate_calendar(profile, days=days, topics=topic_list)
    table = Table(title=f"Content Calendar ({days} days)")
    table.add_column("Date", style="cyan")
    table.add_column("Platform", style="magenta")
    table.add_column("Type", style="green")
    table.add_column("Topic", style="white")

    for entry in calendar:
        table.add_row(
            entry.get("date", ""),
            entry.get("platform", ""),
            entry.get("content_type", ""),
            entry.get("topic", ""),
        )
    console.print(table)


# --- Auth ---


@auth_app.command("login")
def auth_login() -> None:
    """Sign in to OpenAI via OAuth to access Codex."""
    from social_agent.auth import authorize
    settings = get_settings()
    client_id = settings.openai_oauth_client_id

    if not client_id:
        console.print(
            "[red]OPENAI_OAUTH_CLIENT_ID not set.[/red]\n"
            "Add it to your .env file or export it as an environment variable.\n"
            "Register your app at https://platform.openai.com/settings/apps"
        )
        raise typer.Exit(1)

    try:
        tokens = authorize(client_id)
        console.print("[green]✓[/green] Signed in to OpenAI successfully.")
        if "scope" in tokens:
            console.print(f"  [dim]Scopes: {tokens['scope']}[/dim]")
    except Exception as e:
        console.print(f"[red]OAuth sign-in failed:[/red] {e}")
        raise typer.Exit(1)


@auth_app.command("logout")
def auth_logout() -> None:
    """Remove stored OpenAI OAuth tokens."""
    from social_agent.auth import logout
    if logout():
        console.print("[green]✓[/green] OpenAI OAuth tokens removed.")
    else:
        console.print("[dim]No stored tokens found.[/dim]")


@auth_app.command("status")
def auth_status() -> None:
    """Check current OpenAI auth status."""
    from social_agent.auth import _load_tokens, _tokens_expired
    settings = get_settings()

    table = Table(title="Auth Status")
    table.add_column("Method", style="cyan")
    table.add_column("Status", style="white")

    # OAuth
    if settings.openai_oauth_client_id:
        tokens = _load_tokens()
        if tokens and not _tokens_expired(tokens):
            table.add_row("OpenAI OAuth", "[green]Active[/green]")
        elif tokens:
            table.add_row("OpenAI OAuth", "[yellow]Expired (will auto-refresh)[/yellow]")
        else:
            table.add_row("OpenAI OAuth", "[red]Not signed in (run: social-agent auth login)[/red]")
    else:
        table.add_row("OpenAI OAuth", "[dim]Not configured (set OPENAI_OAUTH_CLIENT_ID)[/dim]")

    # API Key
    if settings.openai_api_key:
        masked = settings.openai_api_key[:8] + "..." + settings.openai_api_key[-4:]
        table.add_row("OpenAI API Key", f"[green]Set[/green] ({masked})")
    else:
        table.add_row("OpenAI API Key", "[dim]Not set[/dim]")

    console.print(table)


# --- Dashboard ---


@app.command()
def dashboard() -> None:
    """Launch the Streamlit web dashboard."""
    console.print("[cyan]Launching dashboard at http://localhost:8501...[/cyan]")
    dashboard_path = Path(__file__).parent / "dashboard" / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard_path)])


# --- Agent (interactive) ---


@app.command()
def agent(
    profile_path: str = typer.Option(None, "--profile", help="Path to influencer profile"),
) -> None:
    """Interactive chat mode with the content agent."""
    profile = load_profile(profile_path)
    console.print(Panel(
        f"[bold]Social Media Agent[/bold] for {profile.brand.name}\n"
        f"Type your request or 'quit' to exit.",
        border_style="cyan",
    ))

    from social_agent.agent import run_agent

    while True:
        try:
            user_input = console.input("[bold cyan]> [/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("quit", "exit", "q"):
            break

        if not user_input.strip():
            continue

        with console.status("[cyan]Thinking...[/cyan]"):
            response = run_agent(user_input, profile)

        console.print(Panel(response, border_style="green"))


if __name__ == "__main__":
    app()
