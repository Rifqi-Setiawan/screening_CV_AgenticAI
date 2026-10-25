"""Validation and consistency checking for Profiler Agent output (v2.1)."""

from __future__ import annotations

from typing import Any

from src.agents.schemas.profiler import (
    DomainAllocationLevel,
    ProfilerOutput,
)
from src.domain.atoms import EvidenceAtom
from src.domain.ontology.graph import OntologyGraph


def validate_profiler_output(
    output: ProfilerOutput | dict[str, Any],
    atoms: list[EvidenceAtom | dict[str, Any]],
    ontology: OntologyGraph | None = None,
) -> ProfilerOutput:
    """Validates Profiler output against evidence atoms and capability ontology.

    Performs:
    1. Referential validation:
       - atom_id exists in provided atoms (either by atom_key or id).
       - concepts exist in ontology graph or are marked 'unmapped:<term>'.
    2. Code-atom ratio cross-validation:
       - code_atom_ratio = count(support_atom_ids) / count(total_atoms_in_experience).
       - If allocation level is PRIMARY but code_atom_ratio < 0.3, flag INCONSISTENT_ALLOCATION.
    """
    validated_output = ProfilerOutput.model_validate(output) if isinstance(output, dict) else output

    # Build atom indexes
    valid_atom_keys: set[str] = set()
    valid_atom_ids: set[str] = set()
    atoms_by_exp: dict[str, list[Any]] = {}

    for a in atoms:
        akey = getattr(a, "atom_key", None) or (a.get("atom_key") if isinstance(a, dict) else None)
        aid = getattr(a, "id", None) or (a.get("id") if isinstance(a, dict) else None)
        eref = getattr(a, "entry_ref", None) or (a.get("entry_ref") if isinstance(a, dict) else None)

        if akey:
            valid_atom_keys.add(str(akey))
        if aid:
            valid_atom_ids.add(str(aid))

        if eref:
            atoms_by_exp.setdefault(str(eref), []).append(a)

    # 1. Referential check for atom_tags
    for tag in validated_output.atom_tags:
        tid = str(tag.atom_id)
        if tid not in valid_atom_keys and tid not in valid_atom_ids:
            flag = f"INVALID_ATOM_REF:{tid}"
            if flag not in validated_output.flags:
                validated_output.flags.append(flag)

        # Concepts referential check
        if ontology is not None:
            for concept_id in tag.concepts:
                c_clean = concept_id.strip()
                if c_clean.startswith("unmapped:"):
                    continue
                # Lookup in ontology
                if not ontology.get_concept(c_clean) and not ontology.find_by_alias(c_clean):
                    flag = f"UNKNOWN_CONCEPT:{c_clean}"
                    if flag not in validated_output.flags:
                        validated_output.flags.append(flag)

    # 2. Cross-validation for experience domain allocations
    for exp in validated_output.experiences:
        exp_atoms = atoms_by_exp.get(exp.entry_ref, [])
        total_exp_atoms = len(exp_atoms)

        for alloc in exp.domain_allocations:
            # Match support atom IDs to this experience's atoms
            valid_support = [
                sid for sid in alloc.support_atom_ids if str(sid) in valid_atom_keys or str(sid) in valid_atom_ids
            ]

            if total_exp_atoms > 0:
                calc_ratio = round(len(valid_support) / float(total_exp_atoms), 4)
                alloc.code_atom_ratio = min(1.0, calc_ratio)
            else:
                alloc.code_atom_ratio = 0.0

            # INCONSISTENT_ALLOCATION rule:
            # If PRIMARY allocation has code_atom_ratio < 0.3
            is_primary = alloc.level in (DomainAllocationLevel.PRIMARY, "PRIMARY")
            if is_primary and alloc.code_atom_ratio < 0.3:
                if "INCONSISTENT_ALLOCATION" not in alloc.flags:
                    alloc.flags.append("INCONSISTENT_ALLOCATION")
                if "INCONSISTENT_ALLOCATION" not in validated_output.flags:
                    validated_output.flags.append("INCONSISTENT_ALLOCATION")

    return validated_output
