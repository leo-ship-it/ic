import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from data_source.slack_findings_failover.parse_format import get_current_iso_timestamp, project_to_list_item
from integration.slack.slack_block_kit_utils import (
    BlockKitListHeadline,
    BlockKitListItem,
    BlockKitRichText,
    block_kit_bullet_list_with_headline,
    block_kit_header,
    block_kit_section_with_two_cols,
)


@dataclass
class SlackScanResult:
    new_vulnerabilities: int = 0
    changed_vulnerabilities: int = 0
    fixed_vulnerabilities: int = 0
    unrated_vulnerabilities: int = 0
    total_vulnerabilities: int = 0
    added_dependencies: Dict[Tuple[str, str, str, str], Set[str]] = field(default_factory=lambda: {})
    removed_dependencies: Dict[Tuple[str, str, str, str], Set[str]] = field(default_factory=lambda: {})
    unrated_vulnerabilities_reminder: Dict[str, Tuple[Optional[str], Set[str]]] = field(default_factory=lambda: {})

    def has_updates(self):
        return (
            self.new_vulnerabilities > 0
            or self.changed_vulnerabilities > 0
            or self.fixed_vulnerabilities > 0
            or len(self.added_dependencies) > 0
            or len(self.removed_dependencies) > 0
            or len(self.unrated_vulnerabilities_reminder) > 0
        )

    def add_unrated_vulnerabilities_reminder(self, vuln_id: str, permalink: Optional[str], risk_assessors: Set[str]):
        if vuln_id in self.unrated_vulnerabilities_reminder:
            raise RuntimeError(f"add_unrated_vulnerabilities_reminder was called twice with the same vuln_id {vuln_id}")
        self.unrated_vulnerabilities_reminder[vuln_id] = (permalink, risk_assessors)

    def get_slack_msg(self, repository: str, scanner: str) -> str:
        block_kit_msg = [
            block_kit_header("Scan Results"),
            block_kit_section_with_two_cols("Repository", repository, "Scanner", scanner),
            block_kit_section_with_two_cols(
                "Time", get_current_iso_timestamp(), "Total Vulnerabilities", str(self.total_vulnerabilities)
            ),
            block_kit_section_with_two_cols(
                "New Vulnerabilities",
                str(self.new_vulnerabilities),
                "Changed Vulnerabilities",
                str(self.changed_vulnerabilities),
            ),
            block_kit_section_with_two_cols(
                "Fixed Vulnerabilities",
                str(self.fixed_vulnerabilities),
                "Unrated Vulnerabilities",
                str(self.unrated_vulnerabilities),
            ),
            block_kit_header("Dependencies"),
        ]
        dep_sections = []
        if len(self.added_dependencies) > 0:
            dep_sections.append(("Added", self.added_dependencies))
        if len(self.removed_dependencies) > 0:
            dep_sections.append(("Removed", self.removed_dependencies))
        if len(dep_sections) > 0:
            for header, deps in dep_sections:
                list_items = []
                for dep_id, projects in deps.items():
                    list_items.append(BlockKitListItem(text=[BlockKitRichText(f"{dep_id[2]} {dep_id[3]}")], indent=0))
                    for proj in projects:
                        list_items.append(project_to_list_item(proj, 1))
                block_kit_msg.append(
                    block_kit_bullet_list_with_headline(BlockKitListHeadline.with_text(header), list_items)
                )
        else:
            block_kit_msg.append(block_kit_bullet_list_with_headline(BlockKitListHeadline.with_text("No changes"), []))
        return json.dumps(block_kit_msg)

    def get_slack_thread_msgs_for_reminder(self) -> List[str]:
        if len(self.unrated_vulnerabilities_reminder) == 0:
            return []

        risk_assessors = set()
        res = []
        for vuln_id, (permalink, ras) in self.unrated_vulnerabilities_reminder.items():
            if permalink:
                res.append(f"<{permalink}|{vuln_id}>")
            else:
                res.append(f"{vuln_id}")
            risk_assessors.update(ras)

        return ["The following findings need risk assessment from " + ", ".join(sorted(list(risk_assessors)))] + res
