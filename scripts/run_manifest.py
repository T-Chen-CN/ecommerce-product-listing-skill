#!/usr/bin/env python3
"""Concurrency-safe run manifest CLI for localized ecommerce listing work."""
import argparse, copy, fcntl, hashlib, json, math, os, re, stat, sys, tempfile, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SCHEMA_VERSION = 4
PLAN_MODES = ("default_full", "custom", "revision")
TASK_SCOPES = ("content", "image", "full")
LANGUAGE_MODES = ("bilingual", "target_only", "chinese")
MODULE_KINDS = ("docx_text", "internal", "non_text")
CHINESE_MARKETS = {"CN", "HK", "MO", "TW"}
MARKET_LANGUAGES = {"JP":"ja"}
HARD_REJECT_REASONS = {"api_error", "file_corrupt", "off_topic", "safety_placeholder", "unrecognizable"}
RETRYABLE_CODES = {"rate_limit", "server_error", "timeout", "network_error", "provider_json_error"}
QA_LABELS = {"green", "yellow", "red"}
TIMING_STAGES = ("wave_0", "wave_1", "wave_2", "total")
SLOT_PLAN_FIELDS = {"slot", "purpose", "prompt", "source_text", "zh_reference", "render_text"}
SLOT_UPDATE_FIELDS = {"purpose", "prompt", "source_text", "zh_reference", "render_text", "status", "file", "provider_error", "qa_label", "hard_reject_reason"}
FACT_FIELDS = {"market", "platform", "category", "brand", "model", "language", "product", "copy", "references", "notes"}
QA_FIELDS = {"mode", "reviewed_at", "reviewed_slot_ids", "reviewed_count", "summary"}
DELIVERY_FIELDS = {"deliverable_slots", "rejected_slots", "docx", "folder", "card"}
TOKEN_FIELDS = {"image_key", "file_token", "block_id"}
ROOT_FIELDS = {"schema_version","manifest_id","generation","revision","created_at","updated_at","run_root","task_scope","plan_mode","expected_count","confirmed_by_user","target_language","docx_language_mode","localization_policy","target_only_approval","module_contracts","requested_docx_modules","short_delivery_approval","delivery_mode","facts","modules","images","qa","tokens","delivery","timings","status"}
IMAGE_FIELDS = {"slot","replaces_slot","attempt","predecessor_slot","purpose","prompt","source_text","zh_reference","render_text","status","file","provider_error","qa_label","hard_reject_reason"}
PROVIDER_ERROR_FIELDS = {"code","message","retryable","provider","request_id","status"}
DOCX_FIELDS = {"token","permalink"}; FOLDER_FIELDS={"permalink"}; CARD_FIELDS={"message_id","send_success"}
TIMING_FIELDS={"seconds","recorded_at"}; MODULE_CONTRACT_FIELDS={"kind"}
POLICY_FIELDS={"docx_language_mode","basis","override"}; OVERRIDE_FIELDS={"approved_by","confirmation_text","recorded_at"}
APPROVAL_FIELDS={"evidence","evidence_digest","approved_count","contract","contract_hash","recorded_at","consumed_at","finalized_revision","finalized_evidence_hash"}
EVIDENCE_FIELDS={"approval_text","expected_count","actual_count","manifest_id","generation","author_id","provider","channel","message_id","captured_at"}
CONTRACT_FIELDS={"manifest_id","generation","expected_count","deliverable_slots","rejected_slots"}


def now(): return datetime.now(timezone.utc).isoformat()
def is_int(v): return isinstance(v, int) and not isinstance(v, bool)
def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def canonical_hash(value): return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def unknown_errors(value,allowed,path):
    if not isinstance(value,dict): return []
    extra=set(value)-allowed
    return [f"{path}: unknown fields: {sorted(extra)}"] if extra else []


def atomic_save(path, data):
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    try: mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError: mode = None
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        if mode is not None: os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target)
        try:
            dfd = os.open(target.parent, os.O_RDONLY)
            try: os.fsync(dfd)
            finally: os.close(dfd)
        except OSError: pass
    except BaseException:
        try: os.unlink(temporary)
        except FileNotFoundError: pass
        raise

save = atomic_save


@contextmanager
def manifest_lock(path):
    lock = Path(str(path) + ".lock"); lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX); yield


def approval_registry_path(args):
    configured=getattr(args,"approval_registry",None) or os.environ.get("RUN_MANIFEST_APPROVAL_REGISTRY")
    if configured:return Path(configured).expanduser()
    state=Path(os.environ.get("XDG_STATE_HOME",Path.home()/".local"/"state"))
    return state/"openclaw"/"run-manifest-short-approvals.json"


def approval_registry_key(provider,channel,message_id):
    return json.dumps([provider,channel,message_id],ensure_ascii=False,separators=(",",":"))


def is_chinese_language(value):
    return isinstance(value, str) and value.lower().replace("_", "-").split("-")[0] == "zh"


def infer_localization(args):
    explicit_language = bool(args.target_language)
    chinese = is_chinese_language(args.target_language) if explicit_language else str(args.market or "").upper() in CHINESE_MARKETS
    target = args.target_language or ("zh-CN" if chinese else MARKET_LANGUAGES.get(str(args.market or "").upper(), "market-default"))
    if args.monolingual:
        confirmation = (args.monolingual_confirmation or "").strip()
        if not confirmation: raise ValueError("--monolingual requires non-empty --monolingual-confirmation from user")
        mode, basis = ("chinese", "chinese_market") if chinese else ("target_only", "explicit_user_override")
        override = {"approved_by":"user","confirmation_text":confirmation,"recorded_at":now()}
    elif chinese:
        mode, basis, override = "chinese", "chinese_language" if explicit_language else "chinese_market", None
    else:
        mode, basis, override = "bilingual", "explicit_non_chinese_language" if explicit_language else "non_chinese_market_default", None
    if args.docx_language_mode:
        if args.docx_language_mode == "target_only" and mode != "target_only": raise ValueError("target_only must use --monolingual with user confirmation")
        if args.docx_language_mode != mode: raise ValueError("docx language mode conflicts with inferred localization policy")
    return target, {"docx_language_mode":mode,"basis":basis,"override":override}


def text_contract_errors(value, require_localized=False, path="value"):
    errors = []
    if isinstance(value, dict):
        keys = {"source_text", "zh_reference", "render_text"}; present = keys & set(value)
        if present and present != keys and require_localized:
            errors.append(f"{path}: bilingual localized text requires source_text, zh_reference, render_text together")
        if present == keys:
            source, zh, render = value.get("source_text"), value.get("zh_reference"), value.get("render_text")
            if not all(isinstance(x, str) for x in (source, zh, render)): errors.append(f"{path}: localized text fields must be strings")
            else:
                if require_localized and not zh.strip(): errors.append(f"{path}.zh_reference must be non-empty for bilingual delivery")
                if zh.strip() and zh.strip() in render: errors.append(f"{path}: zh_reference must not enter render_text or prompt")
        elif require_localized and path.startswith("modules.") and not present:
            errors.append(f"{path}: bilingual module must use source_text/zh_reference/render_text")
        for key, child in value.items(): errors.extend(text_contract_errors(child, require_localized, f"{path}.{key}"))
    elif isinstance(value, list):
        for i, child in enumerate(value): errors.extend(text_contract_errors(child, require_localized, f"{path}[{i}]"))
    return errors

def cjk_fragments(text):
    if not isinstance(text,str): return []
    fragments=[]
    for run in re.findall(r"[\u3400-\u9fff]{2,}",text):
        fragments.extend(run[i:j] for i in range(len(run)) for j in range(i+2,len(run)+1))
    return fragments

def language_base(value):
    return value.lower().replace("_", "-").split("-")[0] if isinstance(value,str) else ""

def has_han(text): return isinstance(text,str) and bool(re.search(r"[\u3400-\u9fff]",text))

def prompt_contract_errors(value,path="value",target_language=None):
    errors=[]
    if isinstance(value,dict):
        refs=[]
        def collect(v):
            if isinstance(v,dict):
                for k,x in v.items():
                    if k=="zh_reference" and isinstance(x,str): refs.append(x)
                    collect(x)
            elif isinstance(v,list):
                for x in v:collect(x)
        collect(value)
        fragments={f for ref in refs for f in cjk_fragments(ref)}
        def inspect(v,p):
            if isinstance(v,dict):
                for k,x in v.items():
                    if "prompt" in k.lower():
                        texts=[]
                        def strings(y):
                            if isinstance(y,str):texts.append(y)
                            elif isinstance(y,dict):
                                for z in y.values():strings(z)
                            elif isinstance(y,list):
                                for z in y:strings(z)
                        strings(x)
                        for text in texts:
                            if any(f in text for f in fragments):errors.append(f"{p}.{k}: prompt leaks zh_reference fragment")
                    inspect(x,f"{p}.{k}")
            elif isinstance(v,list):
                for i,x in enumerate(v):inspect(x,f"{p}[{i}]")
        inspect(value,path)
        # Japanese legitimately uses kanji. For other explicitly non-Chinese targets,
        # fail closed on Han in any prompt/render_text in addition to source isolation.
        if language_base(target_language) not in {"", "zh", "ja"}:
            def inspect_han(v,p):
                if isinstance(v,dict):
                    for k,x in v.items():
                        if k == "render_text" or "prompt" in k.lower():
                            texts=[]
                            def strings(y):
                                if isinstance(y,str): texts.append(y)
                                elif isinstance(y,dict):
                                    for z in y.values(): strings(z)
                                elif isinstance(y,list):
                                    for z in y: strings(z)
                            strings(x)
                            if any(has_han(t) for t in texts): errors.append(f"{p}.{k}: Han text forbidden for target_language={target_language}")
                        inspect_han(x,f"{p}.{k}")
                elif isinstance(v,list):
                    for i,x in enumerate(v): inspect_han(x,f"{p}[{i}]")
            inspect_han(value,path)
    return errors


def approval_override_errors(value,path):
    errors=unknown_errors(value,OVERRIDE_FIELDS,path)
    if not isinstance(value.get("approved_by"),str) or not value.get("approved_by","").strip():errors.append(f"{path}.approved_by must be non-empty string")
    if not isinstance(value.get("confirmation_text"),str) or not value.get("confirmation_text","").strip():errors.append(f"{path}.confirmation_text must be non-empty string")
    if not is_timezone_datetime(value.get("recorded_at")):errors.append(f"{path}.recorded_at must be datetime with timezone")
    return errors


def slot_shape(n, replaces_slot=None, purpose=None, attempt=1, predecessor_slot=None):
    return {"slot": n, "replaces_slot": replaces_slot, "attempt":attempt, "predecessor_slot":predecessor_slot, "purpose": purpose, "prompt": None, "status": "pending",
            "file": None, "provider_error": None, "qa_label": None, "hard_reject_reason": None}


def structural_errors(data):
    if not isinstance(data, dict): return ["manifest root must be an object"]
    errors = []
    errors.extend(unknown_errors(data,ROOT_FIELDS,"manifest"))
    if data.get("schema_version") != SCHEMA_VERSION: errors.append(f"unsupported schema_version {data.get('schema_version')!r}; expected {SCHEMA_VERSION}")
    if not is_int(data.get("revision")) or data.get("revision", -1) < 0: errors.append("revision must be a non-negative integer")
    if not isinstance(data.get("manifest_id"), str) or not data.get("manifest_id", "").strip(): errors.append("manifest_id must be non-empty")
    if not is_int(data.get("generation")) or data.get("generation", 0) < 1: errors.append("generation must be positive")
    scope = data.get("task_scope")
    if scope not in TASK_SCOPES: errors.append("task_scope must be content, image, or full")
    expected = data.get("expected_count")
    if not is_int(expected) or expected < 0: errors.append("expected_count must be a non-negative integer")
    elif scope == "content" and expected != 0: errors.append("content scope expected_count must be 0")
    elif scope in {"image", "full"} and expected < 1: errors.append("image/full scope expected_count must be >= 1")
    if data.get("plan_mode") not in PLAN_MODES: errors.append("plan_mode must be default_full, custom, or revision")
    if data.get("docx_language_mode") not in LANGUAGE_MODES: errors.append("docx_language_mode must be bilingual, target_only, or chinese")
    if not isinstance(data.get("target_language"), str) or not data.get("target_language", "").strip(): errors.append("target_language must be non-empty")
    policy=data.get("localization_policy")
    if not isinstance(policy,dict) or policy.get("docx_language_mode")!=data.get("docx_language_mode") or not isinstance(policy.get("basis"),str): errors.append("localization_policy must record mode and basis")
    else:
        errors.extend(unknown_errors(policy,POLICY_FIELDS,"localization_policy"))
        override=policy.get("override")
        if override is not None and not isinstance(override,dict):errors.append("localization_policy.override must be object or null")
        elif isinstance(override,dict):errors.extend(approval_override_errors(override,"localization_policy.override"))
    run_root=data.get("run_root")
    if not isinstance(run_root,str) or not Path(run_root).is_absolute():errors.append("run_root must be an absolute path")
    if not isinstance(data.get("module_contracts"),dict): errors.append("module_contracts must be an object")
    elif any(not isinstance(k,str) or not k or v not in MODULE_KINDS for k,v in data["module_contracts"].items()): errors.append("module_contracts.<name> must be a MODULE_KINDS string")
    if not isinstance(data.get("requested_docx_modules"),list) or not all(isinstance(x,str) and x for x in data.get("requested_docx_modules",[])): errors.append("requested_docx_modules must be string array")
    for field in ("facts", "modules", "qa", "tokens", "delivery", "timings"):
        if not isinstance(data.get(field), dict): errors.append(f"{field} must be an object")
    if isinstance(data.get("facts"),dict):errors.extend(unknown_errors(data["facts"],FACT_FIELDS,"facts"))
    target_approval=data.get("target_only_approval")
    if target_approval is not None and not isinstance(target_approval,dict):errors.append("target_only_approval must be object or null")
    elif isinstance(target_approval,dict):errors.extend(approval_override_errors(target_approval,"target_only_approval"))
    images = data.get("images")
    if not isinstance(images, list): errors.append("images must be an array"); images = []
    valid = []
    for i, image in enumerate(images):
        if not isinstance(image, dict): errors.append(f"images[{i}] must be an object"); continue
        errors.extend(unknown_errors(image,IMAGE_FIELDS,f"images[{i}]"))
        slot = image.get("slot"); replaces = image.get("replaces_slot")
        if not is_int(slot) or slot < 1: errors.append(f"images[{i}].slot must be positive integer (bool forbidden)")
        else: valid.append(image)
        if replaces is not None and (not is_int(replaces) or replaces < 1): errors.append(f"images[{i}].replaces_slot must be positive integer or null")
        if not is_int(image.get("attempt")) or image.get("attempt",0)<1:errors.append(f"images[{i}].attempt must be positive integer")
        pred=image.get("predecessor_slot")
        if pred is not None and (not is_int(pred) or pred<1):errors.append(f"images[{i}].predecessor_slot must be positive integer or null")
        pe=image.get("provider_error")
        if pe is not None and not isinstance(pe,dict): errors.append(f"images[{i}].provider_error must be object or null")
        elif isinstance(pe,dict):errors.extend(unknown_errors(pe,PROVIDER_ERROR_FIELDS,f"images[{i}].provider_error"))
    ids = [x["slot"] for x in valid]
    if len(ids) != len(set(ids)): errors.append("image slot identities must be unique")
    known = {x["slot"]: x for x in valid}
    if is_int(expected):
        contracted = set(range(1, expected + 1))
        if not contracted.issubset(known): errors.append(f"images must contain contracted slots 1..{expected}")
        for image in valid:
            if image["slot"] in contracted and image.get("replaces_slot") is not None: errors.append("contracted slot cannot be a replacement")
            if image["slot"] in contracted and (image.get("attempt") != 1 or image.get("predecessor_slot") is not None): errors.append(f"replacement lineage: contracted slot {image['slot']} must be attempt 1 with no predecessor")
            if image["slot"] not in contracted:
                target = image.get("replaces_slot")
                if target not in contracted: errors.append(f"replacement lineage: slot {image['slot']} must target a contracted root")
        for root in contracted:
            chain=sorted((x for x in valid if x["slot"]==root or x.get("replaces_slot")==root),key=lambda x:x.get("attempt",0))
            for position,node in enumerate(chain,1):
                predecessor=None if position==1 else chain[position-2]["slot"]
                if node.get("attempt")!=position or node.get("predecessor_slot")!=predecessor:
                    errors.append(f"replacement lineage for root {root} must have continuous attempts and direct predecessors")
    qa = data.get("qa")
    if isinstance(qa, dict):
        errors.extend(unknown_errors(qa,QA_FIELDS,"qa"))
        if not isinstance(qa.get("mode"), str): errors.append("qa.mode must be string")
        if qa.get("reviewed_at") is not None and not isinstance(qa.get("reviewed_at"), str): errors.append("qa.reviewed_at must be string or null")
        ids = qa.get("reviewed_slot_ids")
        if not isinstance(ids, list) or not all(is_int(x) and x >= 1 for x in ids): errors.append("qa.reviewed_slot_ids must be integer array")
        if not is_int(qa.get("reviewed_count")) or qa.get("reviewed_count", -1) < 0: errors.append("qa.reviewed_count must be non-negative integer")
    delivery = data.get("delivery")
    if isinstance(delivery, dict):
        errors.extend(unknown_errors(delivery,DELIVERY_FIELDS,"delivery"))
        for field in ("docx", "folder", "card"):
            if not isinstance(delivery.get(field), dict): errors.append(f"delivery.{field} must be object")
        if isinstance(delivery.get("docx"),dict):errors.extend(unknown_errors(delivery["docx"],DOCX_FIELDS,"delivery.docx"))
        if isinstance(delivery.get("folder"),dict):errors.extend(unknown_errors(delivery["folder"],FOLDER_FIELDS,"delivery.folder"))
        if isinstance(delivery.get("card"),dict):errors.extend(unknown_errors(delivery["card"],CARD_FIELDS,"delivery.card"))
        for field in ("deliverable_slots", "rejected_slots"):
            values = delivery.get(field)
            if not isinstance(values, list) or not all(is_int(v) and v >= 1 for v in values): errors.append(f"delivery.{field} must be positive integer array")
    timings = data.get("timings")
    if isinstance(timings, dict):
        for key, value in timings.items():
            if key not in TIMING_STAGES:errors.append(f"timings: unknown field {key!r}")
            if not isinstance(value, dict): errors.append(f"timings.{key} must be object")
            else:errors.extend(unknown_errors(value,TIMING_FIELDS,f"timings.{key}"))
    contracts=data.get("module_contracts")
    tokens=data.get("tokens")
    if isinstance(tokens,dict):
        for key,value in tokens.items():
            if not isinstance(value,dict): errors.append(f"tokens.{key} must be object")
            else:errors.extend(unknown_errors(value,TOKEN_FIELDS,f"tokens.{key}"))
    approval=data.get("short_delivery_approval")
    if approval is not None and not isinstance(approval,dict): errors.append("short_delivery_approval must be object or null")
    elif isinstance(approval,dict):
        errors.extend(unknown_errors(approval,APPROVAL_FIELDS,"short_delivery_approval"))
        evidence=approval.get("evidence")
        if not isinstance(evidence,dict): errors.append("short_delivery_approval.evidence must be object")
        else:
            errors.extend(unknown_errors(evidence,EVIDENCE_FIELDS,"short_delivery_approval.evidence"))
            if approval.get("evidence_digest") != canonical_hash(evidence): errors.append("short_delivery_approval evidence_digest mismatch")
            if evidence.get("manifest_id")!=data.get("manifest_id") or evidence.get("generation")!=data.get("generation") or evidence.get("expected_count")!=data.get("expected_count") or evidence.get("actual_count")!=approval.get("approved_count"): errors.append("short_delivery_approval evidence identity/count mismatch")
            if not is_timezone_datetime(evidence.get("captured_at")): errors.append("short_delivery_approval evidence captured_at must include timezone")
        contract=approval.get("contract")
        if isinstance(contract,dict):
            errors.extend(unknown_errors(contract,CONTRACT_FIELDS,"short_delivery_approval.contract"))
            if contract.get("manifest_id")!=data.get("manifest_id") or contract.get("generation")!=data.get("generation") or contract.get("expected_count")!=data.get("expected_count"):errors.append("short_delivery_approval contract identity does not match manifest")
            if approval.get("contract_hash")!=canonical_hash(contract):errors.append("short_delivery_approval contract_hash mismatch")
        else:errors.append("short_delivery_approval.contract must be object")
    errors.extend(text_contract_errors(data.get("facts", {}), False, "facts"))
    errors.extend(text_contract_errors(data.get("modules", {}), False, "modules"))
    errors.extend(text_contract_errors(images, False, "images"))
    errors.extend(prompt_contract_errors(images,"images",data.get("target_language")))
    return errors


def check_schema(data):
    errors = structural_errors(data)
    if errors: raise ValueError("; ".join(errors))


def mutate(path, updater, expected_revision=None, expected_manifest_id=None, expected_generation=None):
    with manifest_lock(path):
        data = load(path); check_schema(data)
        if expected_revision is not None and expected_revision != data["revision"]: raise ValueError(f"revision conflict: expected {expected_revision}, actual {data['revision']}")
        if ((expected_manifest_id is not None and expected_manifest_id != data["manifest_id"]) or
            (expected_generation is not None and expected_generation != data["generation"])): raise ValueError("manifest identity conflict: stale manifest_id or generation")
        candidate = copy.deepcopy(data); updater(candidate); candidate["revision"] = data["revision"] + 1; candidate["updated_at"] = now()
        check_schema(candidate); atomic_save(path, candidate); return candidate


def identity(args): return (getattr(args, "revision", None), getattr(args, "manifest_id", None), getattr(args, "generation", None))
def mutate_args(args, updater):
    values=identity(args)
    if any(x is None for x in values):
        if not all(x is None for x in values):raise ValueError("manifest_id, generation, and revision must all be provided")
        if not getattr(args,"from_current",False):raise ValueError("mutation requires manifest_id, generation, and revision")
        if args.command not in {"put-module","timing"}:raise ValueError("--from-current is only allowed for atomic field-specific append operations")
    return mutate(args.manifest, updater, *values)


def json_value(raw):
    try: return json.loads(raw)
    except json.JSONDecodeError as e: raise argparse.ArgumentTypeError(f"invalid JSON: {e}") from e


def reject_unknown(value, allowed, label):
    if not isinstance(value, dict): raise ValueError(f"{label} JSON must be an object")
    unknown = set(value) - allowed
    if unknown: raise ValueError(f"{label} unknown fields: {sorted(unknown)}")


def cmd_init(args):
    scope = args.task_scope
    expected = 0 if scope == "content" else (args.expected_count if args.expected_count is not None else 9)
    if scope == "content" and args.expected_count not in (None, 0): raise ValueError("content scope does not create an image contract")
    if scope != "content" and args.plan_mode != "default_full" and (args.expected_count is None or not args.confirmed_by_user): raise ValueError("custom/revision image plan requires --expected-count and --confirmed-by-user")
    if scope != "content" and args.plan_mode == "default_full" and expected != 9: raise ValueError("default_full expected_count is 9")
    if not is_int(expected) or expected < 0: raise ValueError("expected_count invalid")
    # Legacy target-only flags are normalized to the explicit monolingual policy.
    if args.target_only_approved_by_user:
        args.monolingual=True; args.monolingual_confirmation=args.target_only_confirmation
    target, policy = infer_localization(args); mode=policy["docx_language_mode"]
    evidence = policy["override"]
    with manifest_lock(args.manifest):
        path = Path(args.manifest); old_revision, generation = -1, 0
        if path.exists():
            if not args.force: raise ValueError("manifest already exists; use --force")
            old = load(path)
            if not isinstance(old,dict):raise ValueError("existing manifest must be an object")
            if old.get("schema_version") == SCHEMA_VERSION:check_schema(old)
            elif old.get("schema_version") != 3:raise ValueError("--force can rebuild only schema v3 or current v4 manifest")
            old_revision,generation=old.get("revision"),old.get("generation")
            if not is_int(old_revision) or old_revision<0:raise ValueError("existing revision must be a non-negative integer")
            if not is_int(generation) or generation<1:raise ValueError("existing generation must be a positive integer")
        data = {"schema_version":SCHEMA_VERSION,"manifest_id":str(uuid.uuid4()),"generation":generation+1,"revision":old_revision+1,"created_at":now(),"run_root":str(Path(args.manifest).resolve().parent),
                "task_scope":scope,"plan_mode":args.plan_mode,"expected_count":expected,"confirmed_by_user":bool(scope=="content" or args.confirmed_by_user or args.plan_mode=="default_full"),
                "target_language":target,"docx_language_mode":mode,"localization_policy":policy,"target_only_approval":evidence,"module_contracts":{name:"docx_text" for name in args.requested_module},"requested_docx_modules":list(dict.fromkeys(args.requested_module)),"short_delivery_approval":None,"delivery_mode":args.delivery_mode,
                "facts":{"market":args.market,"platform":args.platform,"category":args.category},"modules":{},"images":[slot_shape(n) for n in range(1,expected+1)],
                "qa":{"mode":f"{expected}-image-single-round","reviewed_at":None,"reviewed_slot_ids":[],"reviewed_count":0},"tokens":{},
                "delivery":{"deliverable_slots":[],"rejected_slots":[],"docx":{"token":None,"permalink":None},"folder":{"permalink":None},"card":{"message_id":None,"send_success":False}},"timings":{},"status":"initialized"}
        check_schema(data); atomic_save(path,data)


def cmd_set_facts(args):
    reject_unknown(args.json, FACT_FIELDS, "facts"); errors=text_contract_errors(args.json)
    if errors: raise ValueError("; ".join(errors))
    mutate_args(args, lambda d:d["facts"].update(args.json))


def cmd_set_image_plan(args):
    if not isinstance(args.json,list): raise ValueError("image plan must be array")
    def updater(data):
        by={x["slot"]:x for x in data["images"]}
        for raw in args.json:
            reject_unknown(raw,SLOT_PLAN_FIELDS,"image plan")
            slot=raw.get("slot")
            if not is_int(slot) or slot not in by: raise ValueError("image plan requires known integer slot")
            patch=dict(raw); patch.pop("slot"); errors=text_contract_errors(patch)+prompt_contract_errors(raw,"image plan",data.get("target_language"))
            if errors: raise ValueError("; ".join(errors))
            by[slot].update(patch)
    mutate_args(args,updater)


def cmd_add_replacement(args):
    if not is_int(args.replaces_slot): raise ValueError("replaces_slot must be integer")
    def updater(data):
        target=next((x for x in data["images"] if x["slot"]==args.replaces_slot),None)
        if target is None or args.replaces_slot>data["expected_count"] or target.get("status")!="rejected": raise ValueError("replaces_slot must point to a rejected contracted slot")
        lineage=[x for x in data["images"] if x["slot"]==args.replaces_slot or x.get("replaces_slot")==args.replaces_slot]
        existing=[x for x in lineage if x["slot"]!=args.replaces_slot and x.get("status") in {"pending","success"}]
        if existing: raise ValueError("contracted slot already has one active final replacement")
        predecessor=max(lineage,key=lambda x:x["attempt"])
        data["images"].append(slot_shape(max(x["slot"] for x in data["images"])+1,args.replaces_slot,args.purpose,predecessor["attempt"]+1,predecessor["slot"]))
    mutate_args(args,updater)


def cmd_put_module(args):
    if not isinstance(args.json,dict): raise ValueError("module must be object")
    kind=args.module_kind
    data=load(args.manifest);check_schema(data)
    if data["task_scope"] in {"content","full"} and kind=="docx_text" and args.name not in data["module_contracts"]: raise ValueError("docx_text module must be predeclared at init with --requested-module")
    if args.name in data["module_contracts"] and data["module_contracts"][args.name] != kind: raise ValueError("module kind conflicts with predeclared contract")
    require=kind=="docx_text" and data["docx_language_mode"]=="bilingual"
    errors=text_contract_errors(args.json,require,f"modules.{args.name}")
    if kind=="docx_text" and data["docx_language_mode"] in {"target_only","chinese"}:
        if not isinstance(args.json.get("source_text"),str) or not isinstance(args.json.get("render_text"),str):errors.append(f"modules.{args.name}: docx_text requires source_text and render_text")
        if data["docx_language_mode"]=="target_only" and "zh_reference" in args.json:errors.append(f"modules.{args.name}: target_only forbids zh_reference")
    if errors:raise ValueError("; ".join(errors))
    def updater(d):
        if args.from_current and args.name in d["modules"]: raise ValueError(f"module {args.name!r} already exists; --from-current cannot overwrite")
        d["modules"][args.name]=args.json
        if args.name not in d["module_contracts"]: d["module_contracts"][args.name]=kind
    mutate_args(args,updater)

def cmd_update_slot(args):
    if not is_int(args.slot): raise ValueError("slot must be integer")
    reject_unknown(args.json,SLOT_UPDATE_FIELDS,"slot update"); data=load(args.manifest);check_schema(data); errors=text_contract_errors(args.json)+prompt_contract_errors(args.json,"slot update",data.get("target_language"))
    if errors: raise ValueError("; ".join(errors))
    def updater(data):
        slot=next((x for x in data["images"] if x["slot"]==args.slot),None)
        if slot is None: raise ValueError(f"unknown slot {args.slot}")
        slot.update(args.json)
    mutate_args(args,updater)


def cmd_set_qa(args):
    reject_unknown(args.json,QA_FIELDS,"qa")
    reviewed_at=args.json.get("reviewed_at")
    if reviewed_at is not None and not is_timezone_datetime(reviewed_at): raise ValueError("qa.reviewed_at must be datetime with timezone")
    mutate_args(args,lambda d:d["qa"].update(args.json))


def cmd_set_token(args):
    if not is_int(args.slot): raise ValueError("slot must be integer")
    reject_unknown(args.json,TOKEN_FIELDS,"token")
    def updater(data):
        if args.slot not in {x["slot"] for x in data["images"]}: raise ValueError("unknown slot")
        data["tokens"][str(args.slot)]=args.json
    mutate_args(args,updater)


def cmd_set_delivery(args):
    reject_unknown(args.json,DELIVERY_FIELDS,"delivery")
    mutate_args(args,lambda d:d["delivery"].update(args.json))


def cmd_set_short_approval(args):
    identifiers={"provider":args.provider,"channel":args.channel,"message_id":args.message_id,"author_id":args.author_id}
    if not all(is_identifier(v) for v in identifiers.values()):raise ValueError("provider, channel, message_id, and author_id must be structured non-whitespace identifiers")
    if not isinstance(args.approval_text,str) or not args.approval_text.strip(): raise ValueError("approval_text must preserve the approval message or normalized explicit approval")
    if not is_timezone_datetime(args.captured_at): raise ValueError("captured_at must be datetime with timezone")
    registry_path=approval_registry_path(args); registry_key=approval_registry_key(args.provider,args.channel,args.message_id)
    with manifest_lock(str(registry_path)+".registry"):
        if registry_path.exists():
            registry=load(registry_path)
            if not isinstance(registry,dict):raise ValueError("approval registry must be an object")
        else:registry={}
        existing=registry.get(registry_key)
        current=load(args.manifest)
        if existing is not None and (existing.get("manifest_id"),existing.get("generation")) != (current.get("manifest_id"),current.get("generation")):
            raise ValueError("approval message already consumed by another manifest")
        def updater(data):
            if data.get("short_delivery_approval") is not None:raise ValueError("short delivery approval is immutable once recorded")
            covered,deliverable,rejected=slot_classification(data)
            if args.approved_count!=len(covered) or args.approved_count>=data["expected_count"]: raise ValueError("approved_count must equal current short contract coverage")
            required_contract=f"{data['expected_count']}->{args.approved_count}"
            normalized_text=re.sub(r"\s+","",args.approval_text).replace("→","->")
            if not re.search(rf"(?<!\d){re.escape(required_contract)}(?!\d)",normalized_text): raise ValueError(f"approval_text must explicitly bind current {required_contract} contract")
            contract={"manifest_id":data["manifest_id"],"generation":data["generation"],"expected_count":data["expected_count"],"deliverable_slots":deliverable,"rejected_slots":rejected}
            evidence={"approval_text":args.approval_text.strip(),"expected_count":data["expected_count"],"actual_count":args.approved_count,"manifest_id":data["manifest_id"],"generation":data["generation"],**identifiers,"captured_at":args.captured_at}
            data["short_delivery_approval"]={"evidence":evidence,"evidence_digest":canonical_hash(evidence),"approved_count":args.approved_count,"contract":contract,"contract_hash":canonical_hash(contract),"recorded_at":now(),"consumed_at":None,"finalized_revision":None,"finalized_evidence_hash":None}
        result=mutate_args(args,updater)
        registry[registry_key]={"manifest_id":result["manifest_id"],"generation":result["generation"],"evidence_digest":result["short_delivery_approval"]["evidence_digest"],"recorded_at":result["short_delivery_approval"]["recorded_at"]}
        atomic_save(registry_path,registry)


def cmd_timing(args):
    def updater(data):
        if args.from_current and args.stage in data["timings"]: raise ValueError(f"timing {args.stage!r} already exists; --from-current cannot overwrite")
        data["timings"][args.stage]={"seconds":args.seconds,"recorded_at":now()}
    mutate_args(args,updater)
def nonnegative_float(v):
    n=float(v)
    if not math.isfinite(n) or n<0: raise argparse.ArgumentTypeError("seconds must be finite and >= 0")
    return n


def cmd_select_retry(args):
    data=load(args.manifest); check_schema(data)
    print(json.dumps({"slots":[x["slot"] for x in data["images"] if x.get("status")=="failed" and (x.get("provider_error") or {}).get("code") in RETRYABLE_CODES]}))


def resolve_file(value,base):
    if not isinstance(value,(str,os.PathLike)) or not str(value): return None
    p=Path(value); return p if p.is_absolute() else Path(base)/p

def is_readable_regular_file(value,base=Path.cwd()):
    try: p=resolve_file(value,base); return p is not None and p.is_file()
    except OSError:return False
def is_contained_file(value,run_root):
    if not isinstance(value,str) or not value:return False
    raw=Path(value)
    try:
        root=Path(run_root).resolve(strict=True); target=(raw if raw.is_absolute() else root/raw).resolve(strict=True)
        return target.is_relative_to(root) and target.is_file()
    except (OSError,ValueError):return False
def escapes_run_root(value,run_root):
    if not isinstance(value,str) or not value:return False
    try:
        root=Path(run_root).resolve();raw=Path(value);target=(raw if raw.is_absolute() else root/raw).resolve(strict=False)
        return not target.is_relative_to(root)
    except (OSError,ValueError):return True
def has_supported_image_magic(value,base=Path.cwd()):
    p=resolve_file(value,base)
    if p is None or not is_readable_regular_file(value,base):return False
    try:
        with p.open("rb") as h: header=h.read(12)
    except OSError:return False
    return header.startswith(b"\x89PNG\r\n\x1a\n") or header.startswith(b"\xff\xd8\xff") or (header.startswith(b"RIFF") and header[8:12]==b"WEBP") or header.startswith((b"GIF87a",b"GIF89a"))


def is_timezone_datetime(value):
    if not isinstance(value,str) or "T" not in value:return False
    try: dt=datetime.fromisoformat(value.replace("Z","+00:00")); return dt.tzinfo is not None and dt.utcoffset() is not None
    except ValueError:return False

def is_identifier(v):return isinstance(v,str) and len(v)>=6 and not any(c.isspace() for c in v)
def is_feishu_url(v):
    if not isinstance(v,str):return False
    try:p=urlparse(v);host=(p.hostname or "").lower()
    except ValueError:return False
    return p.scheme=="https" and any(host==d or host.endswith("."+d) for d in ("feishu.cn","larksuite.com"))


def slot_classification(data):
    images=data["images"]; expected=data["expected_count"]; contracted={x["slot"]:x for x in images if x["slot"]<=expected}
    replacements={}
    for x in images:
        if x.get("replaces_slot") is not None: replacements.setdefault(x["replaces_slot"],[]).append(x)
    covered,deliverable,rejected=[],[],[]
    for n in range(1,expected+1):
        original=contracted[n]
        if original.get("status")=="success" and original.get("qa_label") in {"green","yellow"}: covered.append(n);deliverable.append(n)
        elif original.get("status")=="rejected" and original.get("qa_label")=="red" and original.get("hard_reject_reason") in HARD_REJECT_REASONS:
            rejected.append(n); successes=[x for x in replacements.get(n,[]) if x.get("status")=="success" and x.get("qa_label") in {"green","yellow"}]
            if len(successes)==1: covered.append(n);deliverable.append(successes[0]["slot"])
    return covered,deliverable,rejected


def validation_errors(data,delivery=False,manifest_dir=Path.cwd()):
    errors=structural_errors(data)
    if errors:return errors
    scope,expected=data["task_scope"],data["expected_count"]
    images=data["images"]; ids={x["slot"] for x in images}
    for x in images:
        n,status,label,reason=x["slot"],x.get("status"),x.get("qa_label"),x.get("hard_reject_reason")
        if label is not None and label not in QA_LABELS:errors.append(f"slot {n}: invalid qa_label")
        if status=="success":
            if label not in {"green","yellow"}:errors.append(f"slot {n}: qa_label red requires status rejected" if label=="red" else f"slot {n}: status success requires qa_label green or yellow")
            if reason:errors.append(f"slot {n}: hard_reject_reason requires qa_label red and status rejected")
            if escapes_run_root(x.get("file"),data["run_root"]):errors.append(f"slot {n}: delivery file must be contained in run_root (no external absolute, .., or symlink escape)")
            elif not is_readable_regular_file(x.get("file"),data["run_root"]):errors.append(f"slot {n}: delivery file must exist and be a readable regular file")
            elif not has_supported_image_magic(x.get("file"),data["run_root"]):errors.append(f"slot {n}: delivery file must have PNG/JPEG/WebP/GIF magic bytes")
        elif status=="rejected":
            if label!="red" or reason not in HARD_REJECT_REASONS:errors.append(f"slot {n}: status rejected requires qa_label red and a hard_reject_reason")
        elif status in {"pending","failed"}:
            if label is not None:errors.append(f"slot {n}: status {status} requires qa_label null")
        else:errors.append(f"slot {n}: unknown status {status!r}")
    require_bilingual=scope in {"content","full"} and data["docx_language_mode"]=="bilingual"
    contracts=data.get("module_contracts",{}); requested=data.get("requested_docx_modules",[])
    for name in requested:
        if (contracts.get(name))!="docx_text":errors.append(f"modules.{name}: requested Docx module contract missing")
        module=data["modules"].get(name)
        if not isinstance(module,dict):errors.append(f"modules.{name}: requested Docx module missing");continue
        if require_bilingual:errors.extend(text_contract_errors(module,True,f"modules.{name}"))
        elif not isinstance(module.get("source_text"),str) or not isinstance(module.get("render_text"),str):errors.append(f"modules.{name}: docx_text requires source_text and render_text")
    if scope in {"content","full"} and not requested:errors.append("content delivery requires at least one requested_docx_module")
    if data["docx_language_mode"]=="target_only" and not is_chinese_language(data["target_language"]):
        ev=data.get("target_only_approval") or {}
        if ev.get("approved_by")!="user" or not str(ev.get("confirmation_text","")).strip():errors.append("target_only requires explicit user approval evidence")
    if not delivery:return errors
    if data.get("status")!="ready":errors.append("delivery status must be ready")
    state=data["delivery"]
    if scope in {"content","full"}:
        docx,folder=state["docx"],state["folder"]
        if not is_identifier(docx.get("token")) or not is_feishu_url(docx.get("permalink")):errors.append("delivery docx token and Feishu permalink required")
        if not is_feishu_url(folder.get("permalink")):errors.append("delivery folder permalink required")
    if scope=="content":
        if images or data["tokens"] or state["deliverable_slots"] or state["rejected_slots"]:errors.append("content scope must not contain image contract or tokens")
        if state["card"].get("send_success") or state["card"].get("message_id"):errors.append("content scope must not require or retain card evidence")
        return errors
    covered,deliverable,rejected=slot_classification(data)
    actual=len(covered)
    if actual>expected:errors.append("contract coverage exceeds expected_count")
    approval=data.get("short_delivery_approval") or {}
    contract={"manifest_id":data["manifest_id"],"generation":data["generation"],"expected_count":expected,"deliverable_slots":deliverable,"rejected_slots":rejected}
    approved=(approval.get("approved_count")==actual and approval.get("contract")==contract and approval.get("contract_hash")==canonical_hash(contract) and isinstance(approval.get("evidence"),dict) and approval.get("evidence_digest")==canonical_hash(approval["evidence"]) and all(is_identifier(approval["evidence"].get(k)) for k in ("provider","channel","message_id","author_id")))
    if actual<expected and not approved:errors.append(f"expected_count={expected} requires contract coverage {expected}/{expected} or structured user approval")
    if actual>=expected and approval:errors.append("short delivery approval only allowed when actual < expected")
    unrelated=[x["slot"] for x in images if x.get("status")=="success" and x["slot"] not in deliverable]
    if unrelated:errors.append(f"unrelated extra success slots are forbidden: {unrelated}")
    nonfinal=[x["slot"] for x in images if x.get("status") in {"pending","failed"}]
    if nonfinal:errors.append(f"pending/failed slots are not final: {nonfinal}")
    if state["deliverable_slots"]!=deliverable:errors.append("delivery.deliverable_slots must match contract coverage")
    if state["rejected_slots"]!=rejected:errors.append("delivery.rejected_slots must match rejected contracted slots")
    qa=data["qa"]; required_review={x["slot"] for x in images if x.get("status") in {"success","rejected"}}
    reviewed=qa.get("reviewed_slot_ids",[])
    if not is_timezone_datetime(qa.get("reviewed_at")):errors.append("qa.reviewed_at must be datetime with timezone")
    if set(reviewed)!=required_review or qa.get("reviewed_count")!=len(reviewed):errors.append("qa reviewed_slot_ids/reviewed_count must cover all final candidates")
    allowed={f"{expected}-image-single-round"};
    if expected==9:allowed.add("nine-image-single-round")
    if qa.get("mode") not in allowed:errors.append(f"qa.mode must be {expected}-image-single-round")
    timings=data["timings"]; seconds={}
    for stage in TIMING_STAGES:
        value=(timings.get(stage) or {}).get("seconds")
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<0:errors.append(f"timings.{stage}.seconds must be finite and >= 0")
        else:seconds[stage]=value
    if len(seconds)==4 and any(seconds["total"]<seconds[x] for x in TIMING_STAGES[:-1]):errors.append("timings.total.seconds must be at least each wave")
    tokens=data["tokens"]
    for key in tokens:
        if key not in {str(x) for x in ids}:errors.append(f"unknown token slot {key!r}")
    mode=data["delivery_mode"]
    for n in deliverable:
        token=tokens.get(str(n),{})
        if not isinstance(token,dict):errors.append(f"slot {n}: token evidence must be object");continue
        if not is_identifier(token.get("image_key")):errors.append(f"slot {n}: image_key required for {mode} delivery; image_key must be non-whitespace and at least 6 characters")
        if mode=="docx" and not is_identifier(token.get("file_token")):errors.append(f"slot {n}: file_token required for docx delivery; file_token must be non-whitespace and at least 6 characters")
    for n in rejected:
        token=tokens.get(str(n),{})
        if isinstance(token,dict) and (token.get("image_key") or token.get("file_token")):errors.append(f"slot {n}: hard-rejected slot must not have tokens")
    if mode=="docx":
        docx,folder=state["docx"],state["folder"]
        if not docx.get("token") or not docx.get("permalink"):errors.append("delivery docx token and permalink required")
        elif not is_identifier(docx.get("token")):errors.append("delivery docx token must be non-whitespace and at least 6 characters")
        elif not is_feishu_url(docx.get("permalink")):errors.append("delivery docx permalink must be HTTPS Feishu/Lark URL")
        if not folder.get("permalink"):errors.append("delivery folder permalink required")
        elif not is_feishu_url(folder.get("permalink")):errors.append("delivery folder permalink must be HTTPS Feishu/Lark URL")
    if mode=="card":
        if any(isinstance(t,dict) and t.get("file_token") for t in tokens.values()) or state["docx"].get("token") or state["docx"].get("permalink") or state["folder"].get("permalink"):errors.append("card delivery must not retain docx or folder evidence")
    card=state["card"]
    if card.get("send_success") is not True or not is_identifier(card.get("message_id")):errors.append("image delivery requires card send_success true and message_id; message_id must be non-whitespace and at least 6 characters")
    if actual<expected and approved:
        finalized_hash=canonical_hash({"revision":approval.get("finalized_revision"),"delivery":contract,"card_message_id":card.get("message_id"),"approval_evidence":approval.get("evidence"),"evidence_digest":approval.get("evidence_digest"),"contract_hash":approval.get("contract_hash")})
        if not is_timezone_datetime(approval.get("consumed_at")) or approval.get("finalized_revision")!=data["revision"] or approval.get("finalized_evidence_hash")!=finalized_hash:errors.append("short approval must be atomically consumed with matching finalized revision/evidence")
    return errors


def cmd_finalize(args):
    def updater(data):
        if data["task_scope"]=="content":
            data["status"]="ready"
        else:
            covered,deliverable,rejected=slot_classification(data); actual=len(covered); expected=data["expected_count"]
            if actual>expected:raise ValueError("overdelivery forbidden")
            approval=data.get("short_delivery_approval") or {}
            if actual<expected:
                contract={"manifest_id":data["manifest_id"],"generation":data["generation"],"expected_count":expected,"deliverable_slots":deliverable,"rejected_slots":rejected}
                if not (approval.get("approved_count")==actual and approval.get("contract")==contract and approval.get("contract_hash")==canonical_hash(contract)):raise ValueError("structured message-evidence short-delivery approval required for current contract")
                if approval.get("consumed_at") is not None:raise ValueError("short-delivery approval already consumed")
                approval["consumed_at"]=now()
                approval["finalized_revision"]=data["revision"]+1
                approval["finalized_evidence_hash"]=canonical_hash({"revision":data["revision"]+1,"delivery":contract,"card_message_id":data["delivery"]["card"].get("message_id"),"approval_evidence":approval.get("evidence"),"evidence_digest":approval.get("evidence_digest"),"contract_hash":approval.get("contract_hash")})
            elif approval:raise ValueError("short approval cannot be consumed at N/N or overdelivery")
            data["delivery"]["deliverable_slots"]=deliverable;data["delivery"]["rejected_slots"]=rejected;data["status"]="ready"
        data["revision"]+=1
        try:errors=validation_errors(data,True,Path(args.manifest).resolve().parent)
        finally:data["revision"]-=1
        if errors:raise ValueError("cannot finalize invalid delivery: "+"; ".join(errors))
    mutate_args(args,updater)


def cmd_validate(args):
    errors=validation_errors(load(args.manifest),args.delivery,Path(args.manifest).resolve().parent)
    if errors:print("\n".join(errors),file=sys.stderr);return 1
    print("manifest valid");return 0


def add_mutation_args(p,json_arg=True):
    p.add_argument("manifest")
    if json_arg:p.add_argument("--json",required=True,type=json_value)
    p.add_argument("--revision",type=int);p.add_argument("--manifest-id");p.add_argument("--generation",type=int);p.add_argument("--from-current",action="store_true",help="blind mutation; reserved for explicitly safe append operations")


def parser():
    root=argparse.ArgumentParser(description=__doc__);sub=root.add_subparsers(dest="command",required=True)
    p=sub.add_parser("init");p.add_argument("manifest");p.add_argument("--task-scope",choices=TASK_SCOPES,default="image");p.add_argument("--plan-mode",choices=PLAN_MODES,default="default_full");p.add_argument("--expected-count",type=int);p.add_argument("--confirmed-by-user",action="store_true");p.add_argument("--requested-module",action="append",default=[]);p.add_argument("--delivery-mode",choices=("docx","card"),default="docx");p.add_argument("--market");p.add_argument("--platform");p.add_argument("--category");p.add_argument("--target-language");p.add_argument("--docx-language-mode",choices=LANGUAGE_MODES);p.add_argument("--monolingual",action="store_true");p.add_argument("--monolingual-confirmation");p.add_argument("--target-only-approved-by-user",action="store_true");p.add_argument("--target-only-confirmation");p.add_argument("--force",action="store_true");p.set_defaults(func=cmd_init)
    for name,func in (("set-facts",cmd_set_facts),("set-image-plan",cmd_set_image_plan),("set-qa",cmd_set_qa),("set-delivery",cmd_set_delivery)):
        p=sub.add_parser(name);add_mutation_args(p);p.set_defaults(func=func)
    p=sub.add_parser("add-replacement-slot",aliases=["add-replacement"]);add_mutation_args(p,False);p.add_argument("--replaces-slot",required=True,type=json_value);p.add_argument("--purpose");p.set_defaults(func=cmd_add_replacement)
    p=sub.add_parser("put-module");add_mutation_args(p);p.add_argument("name");p.add_argument("--module-kind",choices=MODULE_KINDS,default="docx_text");p.set_defaults(func=cmd_put_module)
    p=sub.add_parser("update-slot");add_mutation_args(p);p.add_argument("slot",type=json_value);p.set_defaults(func=cmd_update_slot)
    p=sub.add_parser("set-token");add_mutation_args(p);p.add_argument("slot",type=json_value);p.set_defaults(func=cmd_set_token)
    p=sub.add_parser("set-short-delivery-approval");add_mutation_args(p,False);p.add_argument("--provider",required=True);p.add_argument("--channel",required=True);p.add_argument("--message-id",required=True);p.add_argument("--author-id",required=True);p.add_argument("--approval-text",required=True);p.add_argument("--captured-at",required=True);p.add_argument("--approved-count",required=True,type=int);p.add_argument("--approval-registry",help="local trusted-caller single-consumption registry path (or RUN_MANIFEST_APPROVAL_REGISTRY)");p.set_defaults(func=cmd_set_short_approval)
    p=sub.add_parser("timing");add_mutation_args(p,False);p.add_argument("stage",choices=TIMING_STAGES);p.add_argument("--seconds",required=True,type=nonnegative_float);p.set_defaults(func=cmd_timing)
    p=sub.add_parser("select-retry");p.add_argument("manifest");p.set_defaults(func=cmd_select_retry)
    p=sub.add_parser("finalize");add_mutation_args(p,False);p.set_defaults(func=cmd_finalize)
    p=sub.add_parser("validate");p.add_argument("manifest");p.add_argument("--delivery",action="store_true");p.set_defaults(func=cmd_validate)
    return root


def main():
    args=parser().parse_args()
    try:result=args.func(args)
    except (ValueError,OSError,json.JSONDecodeError,TypeError,AttributeError,KeyError) as e:print(str(e),file=sys.stderr);result=2
    raise SystemExit(result or 0)
if __name__=="__main__":main()
