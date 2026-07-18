#!/usr/bin/env python3
"""OrderSpec Agents Synchronization Orchestrator.

This script manages:
- Detection of installed AI agents
- Synchronization of prompts and skills to enabled agents
- Reading external rules from agents
- State management in .orderspec/state/agents.json
"""
import sys
import os
import json
import argparse
from datetime import datetime, timezone
from typing import Optional

# Add framework to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from adapters.registry import get_all_adapters
from adapters.base import AgentAdapter

STATE_DIR = os.path.join(".orderspec", "state")
STATE_FILE = os.path.join(STATE_DIR, "agents.json")
PROMPTS_SOURCE = os.path.join(".orderspec", "framework", "prompts")
SKILLS_DIR = os.path.join(".orderspec", "skills")


def load_state() -> dict:
    """Load agents state from JSON file."""
    if os.path.isfile(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "version": 1,
        "updated_at": "",
        "enabled_agents": [],
        "agents": {},
        "last_sync": {}
    }


def save_state(state: dict):
    """Save agents state to JSON file."""
    os.makedirs(STATE_DIR, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


def detect_all() -> list:
    """Run detect() on all registered adapters and return list of AgentInfo dicts."""
    project_root = os.getcwd()
    results = []
    for adapter in get_all_adapters():
        info = adapter.detect(project_root)
        if info:
            info_dict = info.to_dict()
            info_dict["subagent_policy"] = adapter.subagent_policy()
            results.append(info_dict)
        else:
            # Include undetected adapters in the list for transparency
            results.append({
                "agent_id": adapter.agent_id,
                "display_name": getattr(adapter, 'display_name', adapter.agent_id),
                "detected": False,
                "detection_reason": "Not found in project",
                "config_paths": [],
                "prompts_dir": "",
                "supports_symlinks": False,
                "rules_files": [],
                "subagent_policy": adapter.subagent_policy(),
            })
    return results


def ensure_skills_dir():
    """Ensure .orderspec/skills/ directory exists."""
    os.makedirs(SKILLS_DIR, exist_ok=True)
    gitkeep = os.path.join(SKILLS_DIR, ".gitkeep")
    if not os.path.exists(gitkeep):
        with open(gitkeep, 'w') as f:
            f.write("")


def sync_agents(enabled_ids: list) -> dict:
    """Synchronize prompts and skills for specified agents.
    
    Updates agents.json state with sync results.
    """
    project_root = os.getcwd()
    state = load_state()

    # Ensure skills directory exists
    ensure_skills_dir()

    report = {
        "sync_results": [],
        "warnings": [],
        "errors": []
    }

    # Update enabled agents list
    state["enabled_agents"] = enabled_ids

    for adapter in get_all_adapters():
        if adapter.agent_id in enabled_ids:
            agent_report = {
                "agent_id": adapter.agent_id,
                "skills_sync": {},
                "prompts_sync": {},
                "rules_read": {},
                "subagents": {},
            }

            # Sync skills dir
            try:
                skills_res = adapter.sync_skills_dir(project_root, SKILLS_DIR)
                agent_report["skills_sync"] = skills_res
            except Exception as e:
                agent_report["skills_sync"] = {"status": "error", "details": str(e)}
                report["errors"].append(f"[{adapter.agent_id}] skills sync: {e}")

            # Sync prompts
            try:
                prompts_res = adapter.sync_prompts(project_root, PROMPTS_SOURCE)
                agent_report["prompts_sync"] = prompts_res

                # Check for stale files warning
                if prompts_res.get("missing_in_source"):
                    report["warnings"].append(
                        f"Agent '{adapter.agent_id}' has files in its prompts dir "
                        f"that are missing in framework source: "
                        f"{', '.join(prompts_res['missing_in_source'])}. "
                        f"Consider manual cleanup."
                    )
            except Exception as e:
                agent_report["prompts_sync"] = {"errors": [str(e)]}
                report["errors"].append(f"[{adapter.agent_id}] prompts sync: {e}")

            # Inspect workers without changing agent configuration. Named
            # worker setup is explicit and handled by the subagents command.
            try:
                agent_report["subagents"] = adapter.inspect_subagents(project_root)
            except Exception as e:
                agent_report["subagents"] = {
                    "agent": adapter.agent_id,
                    "status": "error",
                    "errors": [str(e)],
                }
                report["errors"].append(f"[{adapter.agent_id}] sub-agent inspection: {e}")

            # Update state for this agent
            detect_info = adapter.detect(project_root)
            if detect_info:
                state["agents"][adapter.agent_id] = detect_info.to_dict()
                state["agents"][adapter.agent_id]["subagent_policy"] = adapter.subagent_policy()
                state["agents"][adapter.agent_id]["sync_state"] = {
                    "skills": agent_report["skills_sync"],
                    "prompts": {
                        "copied": agent_report["prompts_sync"].get("copied", []),
                        "skipped": agent_report["prompts_sync"].get("skipped", []),
                        "last_sync": datetime.now(timezone.utc).isoformat()
                    },
                    "subagents": agent_report["subagents"],
                }

            report["sync_results"].append(agent_report)

    # Remove disabled agents from state.agents but keep their sync history
    for agent_id in list(state["agents"].keys()):
        if agent_id not in enabled_ids:
            state["agents"][agent_id]["enabled"] = False

    state["last_sync"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "enabled_agents": enabled_ids
    }

    save_state(state)
    return report


def read_rules(enabled_ids: list) -> dict:
    """Read external rules from specified agents.
    
    Returns combined rules content for bootstrap integration analysis.
    """
    project_root = os.getcwd()
    results = {
        "agents": {},
        "combined_files": [],
        "combined_contents": {}
    }

    for adapter in get_all_adapters():
        if adapter.agent_id in enabled_ids:
            try:
                rules = adapter.read_rules(project_root)
                results["agents"][adapter.agent_id] = rules

                # Merge into combined view
                for filename, content in rules.get("contents", {}).items():
                    if filename not in results["combined_contents"]:
                        results["combined_contents"][filename] = content
                        results["combined_files"].append(filename)
            except Exception as e:
                results["agents"][adapter.agent_id] = {
                    "agent": adapter.agent_id,
                    "errors": [f"Failed to read rules: {e}"]
                }

    return results


def inspect_subagents(agent_id: str, name: Optional[str] = None, scope: str = "project") -> dict:
    """Inspect one agent's worker registry through its adapter."""
    project_root = os.getcwd()
    try:
        adapter = next(a for a in get_all_adapters() if a.agent_id == agent_id)
    except StopIteration:
        return {
            "agent": agent_id,
            "scope": scope,
            "status": "error",
            "errors": [f"Adapter '{agent_id}' not found in registry."],
        }
    return adapter.inspect_subagents(project_root, requested_name=name, scope=scope)


def validate_orderspec_workers(agent_id: str, scope: str = "project") -> dict:
    """Return one deterministic readiness receipt for framework-required workers."""
    try:
        adapter = next(a for a in get_all_adapters() if a.agent_id == agent_id)
    except StopIteration:
        return {
            "ok": False,
            "ready": False,
            "agent": agent_id,
            "error": "adapter_not_found",
        }
    policy = adapter.subagent_policy()
    required_roles = policy.get("required_orderspec_roles", [])
    if not policy.get("supports_subagents"):
        return {
            "ok": True,
            "ready": True,
            "agent": agent_id,
            "verification": "local_only",
            "required_roles": [],
            "workers": [],
        }
    if not required_roles:
        return {
            "ok": True,
            "ready": True,
            "agent": agent_id,
            "verification": "runtime_only",
            "required_roles": [],
            "workers": [],
        }
    workers = []
    ready = True
    for role in required_roles:
        inspection = adapter.inspect_subagents(os.getcwd(), requested_name=role, scope=scope)
        requested = inspection.get("requested", {})
        role_ready = bool(requested.get("configuration_ready"))
        ready = ready and role_ready
        workers.append({
            "name": role,
            "configuration_ready": role_ready,
            "source": requested.get("source"),
            "model": requested.get("model"),
            "reasoning_effort": requested.get("reasoning_effort"),
            "errors": requested.get("errors", inspection.get("errors", [])),
        })
    return {
        "ok": ready,
        "ready": ready,
        "receipt_version": 1,
        "agent": agent_id,
        "scope": scope,
        "verification": "adapter_managed",
        "runtime_compatibility": "must_be_confirmed_by_current_runtime",
        "required_roles": required_roles,
        "workers": workers,
    }


def configure_subagent(
    agent_id: str,
    name: str,
    reasoning_effort: str,
    scope: str = "project",
    description: Optional[str] = None,
    developer_instructions: Optional[str] = None,
    model: Optional[str] = None,
    overwrite: bool = False,
) -> dict:
    """Write one worker definition through the selected adapter."""
    project_root = os.getcwd()
    try:
        adapter = next(a for a in get_all_adapters() if a.agent_id == agent_id)
    except StopIteration:
        return {
            "agent": agent_id,
            "scope": scope,
            "name": name,
            "status": "error",
            "details": f"Adapter '{agent_id}' not found in registry.",
        }
    return adapter.configure_subagent(
        project_root,
        name=name,
        reasoning_effort=reasoning_effort,
        scope=scope,
        description=description,
        developer_instructions=developer_instructions,
        model=model,
        overwrite=overwrite,
    )


def ensure_subagent(
    agent_id: str,
    name: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    scope: str = "project",
    description: str | None = None,
    developer_instructions: str | None = None,
    model: str | None = None,
    overwrite: bool = False,
    interactive: bool = True,
) -> dict:
    """Use an existing worker or interactively configure a missing one."""
    inspection = inspect_subagents(agent_id, name=name, scope=scope)
    if inspection.get("status") in ("error", "unsupported"):
        return inspection

    requested = inspection.get("requested") if name else None
    if requested and requested.get("configured") and requested.get("valid"):
        return {
            "action": "use_existing",
            "status": "ready",
            "inspection": inspection,
            "worker": requested,
        }

    if not interactive:
        missing = name or "worker name"
        return {
            "action": "configure",
            "status": "needs_user_input",
            "inspection": inspection,
            "details": f"No valid worker '{missing}' is configured; provide --name and --reasoning.",
        }

    if not name or (requested and not requested.get("valid")):
        prompt = "Sub-agent name"
        if requested and requested.get("errors"):
            prompt += " (existing definition is invalid; choose a new name)"
        name = input(f"{prompt}: ").strip()
    if not name:
        return {"action": "configure", "status": "error", "details": "Sub-agent name cannot be empty."}

    if not reasoning_effort:
        reasoning_effort = input(
            "Reasoning effort [medium] (none, minimal, low, medium, high, xhigh, max, ultra): "
        ).strip() or "medium"

    return configure_subagent(
        agent_id=agent_id,
        name=name,
        reasoning_effort=reasoning_effort,
        scope=scope,
        description=description,
        developer_instructions=developer_instructions,
        model=model,
        overwrite=overwrite,
    )


def print_text_report(report: dict):
    """Print human-readable sync report."""
    for res in report.get("sync_results", []):
        print(f"\nAgent: {res['agent_id']}")
        print(f"  Skills: {res['skills_sync'].get('status', 'unknown')} — {res['skills_sync'].get('details', '')}")

        prompts = res.get("prompts_sync", {})
        copied = prompts.get("copied", [])
        skipped = prompts.get("skipped", [])
        errors = prompts.get("errors", [])

        print(f"  Prompts copied: {len(copied)}")
        for f in copied:
            print(f"    + {f}")
        print(f"  Prompts skipped (up-to-date): {len(skipped)}")
        if errors:
            print(f"  Errors: {errors}")

        subagents = res.get("subagents", {})
        if subagents:
            print(f"  Sub-agents: {subagents.get('status', 'unknown')}")

    for warn in report.get("warnings", []):
        print(f"\n⚠️  WARNING: {warn}")

    for err in report.get("errors", []):
        print(f"\n❌ ERROR: {err}")


def main():
    parser = argparse.ArgumentParser(
        description="OrderSpec Agents Synchronization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s detect --json
  %(prog)s sync --agents kilocode --json
  %(prog)s sync --agents kilocode claude_code codex
  %(prog)s read-rules --agents kilocode claude_code codex --json
  %(prog)s subagents inspect --agent codex --name orderspec.worker.weak --json
  %(prog)s subagents ensure --agent codex
        """
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # detect
    parser_detect = subparsers.add_parser("detect", help="Detect installed AI agents")
    parser_detect.add_argument("--json", action="store_true", help="Output as JSON")

    # sync
    parser_sync = subparsers.add_parser("sync", help="Sync prompts and skills for enabled agents")
    parser_sync.add_argument("--agents", nargs="+", required=False, help="List of agent_ids to sync. If omitted, runs interactive detection.")
    parser_sync.add_argument("--json", action="store_true", help="Output as JSON")

    # read-rules
    parser_rules = subparsers.add_parser("read-rules", help="Read external rules from agents")
    parser_rules.add_argument("--agents", nargs="+", required=True, help="List of agent_ids to read rules from")
    parser_rules.add_argument("--json", action="store_true", help="Output as JSON")

    # state
    parser_state = subparsers.add_parser("state", help="Show current agents state")
    parser_state.add_argument("--json", action="store_true", help="Output as JSON")

    # subagents
    parser_subagents = subparsers.add_parser(
        "subagents",
        help="Inspect or configure delegated workers through an agent adapter",
    )
    subagent_parsers = parser_subagents.add_subparsers(dest="subagents_command", required=True)

    parser_subagents_inspect = subagent_parsers.add_parser("inspect", help="Inspect configured workers")
    parser_subagents_inspect.add_argument("--agent", required=True, help="Agent adapter id")
    parser_subagents_inspect.add_argument("--name", help="Worker name to validate")
    parser_subagents_inspect.add_argument("--scope", choices=["project", "global"], default="project")
    parser_subagents_inspect.add_argument("--json", action="store_true", help="Output as JSON")

    parser_subagents_validate = subagent_parsers.add_parser(
        "validate-orderspec",
        help="Validate every worker role required by the current OrderSpec framework",
    )
    parser_subagents_validate.add_argument("--agent", required=True, help="Agent adapter id")
    parser_subagents_validate.add_argument("--scope", choices=["project", "global"], default="project")
    parser_subagents_validate.add_argument("--json", action="store_true", help="Output as JSON")

    for action, help_text in (
        ("ensure", "Use an existing worker or configure a missing worker"),
        ("configure", "Create or update one worker definition"),
    ):
        subagent_parser = subagent_parsers.add_parser(action, help=help_text)
        subagent_parser.add_argument("--agent", required=True, help="Agent adapter id")
        subagent_parser.add_argument("--name", required=(action == "configure"), help="Worker name")
        subagent_parser.add_argument("--reasoning", dest="reasoning_effort", required=(action == "configure"), help="Reasoning effort")
        subagent_parser.add_argument("--scope", choices=["project", "global"], default="project")
        subagent_parser.add_argument("--description", help="Optional worker description")
        subagent_parser.add_argument("--developer-instructions", help="Optional worker instructions")
        subagent_parser.add_argument("--model", help="Optional model override")
        subagent_parser.add_argument("--overwrite", action="store_true", help="Replace an existing custom definition")
        subagent_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "detect":
        results = detect_all()
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            for r in results:
                status = "+" if r["detected"] else "-"
                print(f"[{status}] {r['display_name']} ({r['agent_id']}): {r['detection_reason']}")

    elif args.command == "sync":
        enabled_ids = args.agents
        
        if not enabled_ids:
            if args.json:
                print(json.dumps({"error": "Interactive mode requires text output. Remove --json flag."}, indent=2))
                return
            
            print("No --agents flag provided. Running interactive detection...")
            detected = detect_all()
            detected_agents = [a for a in detected if a.get("detected")]
            
            if not detected_agents:
                print("\nNo supported AI agents detected in this project.")
                print("Ensure your agent (e.g., Kilo Code, Claude Code, or Codex) is installed and initialized.")
                return
            
            print("\nDetected AI agents:")
            for i, a in enumerate(detected_agents, 1):
                print(f"  {i}. {a['display_name']} ({a['agent_id']})")
            
            while True:
                choice = input("\nSelect agents to sync (comma-separated numbers, or 'all'): ").strip().lower()
                if not choice:
                    print("No agents selected. Exiting.")
                    return
                if choice == 'all':
                    enabled_ids = [a['agent_id'] for a in detected_agents]
                    break
                try:
                    indices = [int(x.strip()) for x in choice.split(',')]
                    if all(1 <= i <= len(detected_agents) for i in indices):
                        enabled_ids = list(set([detected_agents[i-1]['agent_id'] for i in indices]))
                        break
                    else:
                        print("Invalid selection. Please enter valid numbers.")
                except ValueError:
                    print("Invalid input. Please enter comma-separated numbers or 'all'.")

        report = sync_agents(enabled_ids)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print_text_report(report)

    elif args.command == "read-rules":
        results = read_rules(args.agents)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            for agent_id, rules in results["agents"].items():
                files = rules.get("files", [])
                errors = rules.get("errors", [])
                print(f"\nAgent: {agent_id}")
                if files:
                    print(f"  Rule files found: {', '.join(files)}")
                else:
                    print(f"  No rule files found.")
                if errors:
                    print(f"  Errors: {errors}")

    elif args.command == "state":
        state = load_state()
        if args.json:
            print(json.dumps(state, indent=2, ensure_ascii=False))
        else:
            print(f"Enabled agents: {state.get('enabled_agents', [])}")
            print(f"Last updated: {state.get('updated_at', 'never')}")
            if state.get("last_sync"):
                print(f"Last sync: {state['last_sync'].get('timestamp', 'never')}")
            for agent_id, info in state.get("agents", {}).items():
                enabled = agent_id in state.get("enabled_agents", [])
                print(f"  [{'+'if enabled else '-'}] {agent_id}: prompts_dir={info.get('prompts_dir', '?')}")

    elif args.command == "subagents":
        if args.subagents_command == "inspect":
            result = inspect_subagents(args.agent, args.name, args.scope)
        elif args.subagents_command == "validate-orderspec":
            result = validate_orderspec_workers(args.agent, args.scope)
        elif args.subagents_command == "configure":
            result = configure_subagent(
                agent_id=args.agent,
                name=args.name,
                reasoning_effort=args.reasoning_effort,
                scope=args.scope,
                description=args.description,
                developer_instructions=args.developer_instructions,
                model=args.model,
                overwrite=args.overwrite,
            )
        else:
            result = ensure_subagent(
                agent_id=args.agent,
                name=args.name,
                reasoning_effort=args.reasoning_effort,
                scope=args.scope,
                description=args.description,
                developer_instructions=args.developer_instructions,
                model=args.model,
                overwrite=args.overwrite,
                interactive=not args.json,
            )

        if getattr(args, "json", False):
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.subagents_command == "validate-orderspec" and not result.get("ready"):
            raise SystemExit(2)


if __name__ == "__main__":
    main()
