#!/usr/bin/env python3
"""Concurrency-safe run manifest CLI for localized ecommerce listing work."""
import argparse, copy, fcntl, json, math, os, re, stat, sys, tempfile, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SCHEMA_VERSION = 8
PLAN_MODES = ("default_full", "custom", "revision")
TASK_SCOPES = ("content", "image", "full")
LANGUAGE_MODES = ("bilingual", "target_only", "chinese")
MODULE_KINDS = ("docx_text", "internal", "non_text")
CHINESE_MARKETS = {"CN", "HK", "MO", "TW"}
MARKET_LANGUAGES = {"JP":"ja"}
RETRYABLE_CODES = {"rate_limit", "server_error", "timeout", "network_error", "provider_json_error"}
TIMING_STAGES = ("wave_0", "wave_1", "wave_2", "total")
SLOT_PLAN_FIELDS = {"slot", "purpose", "prompt", "source_text", "zh_reference", "render_text"}
SLOT_UPDATE_FIELDS = {"purpose", "prompt", "source_text", "zh_reference", "render_text", "status", "file", "provider_error", "asset_filename", "image_batch"}
FACT_FIELDS = {"market", "platform", "category", "brand", "model", "language", "product", "copy", "references", "notes"}
DELIVERY_FIELDS = {"deliverable_slots", "failed_slots", "docx", "folder", "card", "directory_chain", "product_folder_token"}
TOKEN_FIELDS = {"image_key", "file_token", "block_id"}
ROOT_FIELDS = {"schema_version","manifest_id","generation","revision","created_at","updated_at","run_root","task_scope","plan_mode","expected_count","confirmed_by_user","target_language","docx_language_mode","localization_policy","target_only_approval","module_contracts","requested_docx_modules","delivery_route","delivery_route_source","delivery_config_schema_version","delivery_override","agent_name","product_slug","market_country_code","drive_path_segments","facts","modules","images","tokens","delivery","timings","status"}
IMAGE_FIELDS = {"slot","purpose","prompt","source_text","zh_reference","render_text","status","file","provider_error","asset_filename","image_batch"}
PROVIDER_ERROR_FIELDS = {"code","message","retryable","provider","request_id","status"}
DOCX_FIELDS = {"token","permalink","docx_filename","docx_batch"}; FOLDER_FIELDS={"token","permalink"}; CARD_FIELDS={"message_id","send_success"}
DIRECTORY_ENTRY_FIELDS = {"name", "token", "type", "parent_token", "resolution", "exact_match_count_first", "exact_match_count_second", "exact_match_count_after", "created", "created_token", "pages_scanned_first", "pages_scanned_second", "pages_scanned_after", "resolved_at"}
TIMING_FIELDS={"seconds","recorded_at"}; MODULE_CONTRACT_FIELDS={"kind"}
POLICY_FIELDS={"docx_language_mode","basis","override"}; OVERRIDE_FIELDS={"approved_by","confirmation_text","recorded_at"}; DELIVERY_OVERRIDE_FIELDS={"delivery_route","confirmation_text","recorded_at"}
ISO_ALPHA2 = set("AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split())


def now(): return datetime.now(timezone.utc).isoformat()
def is_int(v): return isinstance(v, int) and not isinstance(v, bool)
def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def unknown_errors(value,allowed,path):
    if not isinstance(value,dict): return []
    extra=set(value)-allowed
    return [f"{path}: unknown fields: {sorted(extra)}"] if extra else []


def product_slug(product_name, country_code):
    """Create the literal product-name slug used by the delivery directory contract."""
    if not isinstance(product_name, str):
        raise ValueError("product-name must be a string")
    if not isinstance(country_code, str) or country_code.upper() not in ISO_ALPHA2:
        raise ValueError("country-code must be an ISO 2-letter country code")
    if any(ord(char) < 32 or ord(char) == 127 for char in product_name):
        raise ValueError("product-name must not contain control characters")
    body = re.sub(r"\s+", "-", product_name)
    body = re.sub(r'[/\\:*?"<>|]', "", body)
    body = re.sub(r"-+", "-", body).strip("-")
    if not body or body in {".", ".."}:
        raise ValueError("product-name must have a non-empty slug body after sanitization")
    return f"{body}-{country_code.upper()}"


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


def directory_resolution_errors(value, path):
    evidence_fields = DIRECTORY_ENTRY_FIELDS - {"name", "token", "type", "parent_token"}
    errors = [f"{path}: missing resolution evidence fields: {sorted(evidence_fields - set(value))}"] if evidence_fields - set(value) else []
    resolution = value.get("resolution")
    if resolution not in {"reused", "created"}:
        errors.append(f"{path}.resolution must be reused or created")

    counts = {}
    pages = {}
    for stage in ("first", "second", "after"):
        count_field = f"exact_match_count_{stage}"
        pages_field = f"pages_scanned_{stage}"
        count = value.get(count_field)
        page_count = value.get(pages_field)
        counts[stage] = count
        pages[stage] = page_count
        if stage == "first" or count is not None:
            if not is_int(count) or count < 0:
                errors.append(f"{path}.{count_field} must be a non-negative integer")
            elif count > 1:
                errors.append(f"{path}.{count_field} must not exceed 1")
        if stage == "first" or page_count is not None:
            if not is_int(page_count) or page_count < 1:
                errors.append(f"{path}.{pages_field} must be a positive integer for an executed stage")
        if (count is None) != (page_count is None):
            errors.append(f"{path}: {stage} count and pages evidence must both be present or both be null")

    created = value.get("created")
    created_token = value.get("created_token")
    if not isinstance(created, bool):
        errors.append(f"{path}.created must be bool")
    if resolution == "reused":
        if counts["first"] != 1:
            errors.append(f"{path}.exact_match_count_first must equal 1 for reused resolution")
        if created is not False:
            errors.append(f"{path}.created must be false for reused resolution")
        if created_token is not None:
            errors.append(f"{path}.created_token must be null for reused resolution")
    elif resolution == "created":
        if counts != {"first": 0, "second": 0, "after": 1}:
            errors.append(f"{path}: created resolution requires exact match counts first=0, second=0, after=1")
        if created is not True:
            errors.append(f"{path}.created must be true for created resolution")
        if not isinstance(created_token, str) or not created_token.strip():
            errors.append(f"{path}.created_token must be a non-empty string for created resolution")
        elif created_token != value.get("token"):
            errors.append(f"{path}.created_token must equal token for created resolution")
    if not is_timezone_datetime(value.get("resolved_at")):
        errors.append(f"{path}.resolved_at must be datetime with timezone")
    return errors


def approval_override_errors(value,path):
    errors=unknown_errors(value,OVERRIDE_FIELDS,path)
    if not isinstance(value.get("approved_by"),str) or not value.get("approved_by","").strip():errors.append(f"{path}.approved_by must be non-empty string")
    if not isinstance(value.get("confirmation_text"),str) or not value.get("confirmation_text","").strip():errors.append(f"{path}.confirmation_text must be non-empty string")
    if not is_timezone_datetime(value.get("recorded_at")):errors.append(f"{path}.recorded_at must be datetime with timezone")
    return errors


def slot_shape(n):
    return {"slot": n, "purpose": None, "prompt": None, "status": "pending", "file": None, "provider_error": None, "asset_filename": None, "image_batch": None}


def provider_error_shape_errors(value, path, require_core=False):
    errors = unknown_errors(value, PROVIDER_ERROR_FIELDS, path)
    if require_core:
        for field in ("code", "message"):
            if not isinstance(value.get(field), str) or not value[field].strip():
                errors.append(f"{path}.{field} must be non-empty string")
    if "retryable" in value and not isinstance(value["retryable"], bool):
        errors.append(f"{path}.retryable must be bool")
    for field in ("provider", "request_id"):
        if field in value and not isinstance(value[field], str):
            errors.append(f"{path}.{field} must be string")
    if "status" in value and (not is_int(value["status"]) or not 100 <= value["status"] <= 599):
        errors.append(f"{path}.status must be HTTP status integer (100..599)")
    return errors


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
    delivery_route=data.get("delivery_route")
    if delivery_route not in {"docx", "interactive_card"}:errors.append("delivery_route must be docx or interactive_card")
    source=data.get("delivery_route_source")
    if source not in {"skill_config", "bootstrap_result", "explicit_user_override"}:errors.append("delivery_route_source must be skill_config, bootstrap_result, or explicit_user_override")
    if data.get("delivery_config_schema_version") != 1:errors.append("delivery_config_schema_version must equal 1")
    override=data.get("delivery_override")
    if source == "explicit_user_override":
        if not isinstance(override,dict):errors.append("explicit_user_override requires delivery_override user evidence")
        else:
            errors.extend(unknown_errors(override,DELIVERY_OVERRIDE_FIELDS,"delivery_override"))
            if override.get("delivery_route") != delivery_route:errors.append("delivery_override.delivery_route must equal delivery_route")
            if not isinstance(override.get("confirmation_text"),str) or not override.get("confirmation_text","").strip():errors.append("delivery_override.confirmation_text must be non-empty")
            if not is_timezone_datetime(override.get("recorded_at")):errors.append("delivery_override.recorded_at must be datetime with timezone")
    elif override is not None:errors.append("delivery_override must be null unless source is explicit_user_override")
    if delivery_route == "docx":
        if not isinstance(data.get("agent_name"),str) or not data.get("agent_name","").strip():errors.append("agent_name must be non-empty for docx delivery")
        if not isinstance(data.get("product_slug"),str) or not data.get("product_slug","").strip():errors.append("product_slug must be non-empty for docx delivery")
        if data.get("market_country_code") not in ISO_ALPHA2:errors.append("market_country_code must be a valid ISO 3166-1 alpha-2 uppercase code")
        expected_path=[data.get("agent_name"),"电商需求","Listing",data.get("product_slug")]
        if data.get("drive_path_segments") != expected_path:errors.append(f"drive_path_segments must equal {expected_path!r}")
    else:
        for field in ("agent_name","product_slug","market_country_code","drive_path_segments"):
            if field in data:errors.append(f"interactive_card delivery must not contain {field}")
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
    for field in ("facts", "modules", "tokens", "delivery", "timings"):
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
        slot = image.get("slot")
        if not is_int(slot) or slot < 1: errors.append(f"images[{i}].slot must be positive integer (bool forbidden)")
        else: valid.append(image)
        pe=image.get("provider_error")
        if pe is not None and not isinstance(pe,dict): errors.append(f"images[{i}].provider_error must be object or null")
        elif isinstance(pe,dict):errors.extend(provider_error_shape_errors(pe,f"images[{i}].provider_error",image.get("status")=="failed"))
    ids = [x["slot"] for x in valid]
    if len(ids) != len(set(ids)): errors.append("image slot identities must be unique")
    known = {x["slot"]: x for x in valid}
    if is_int(expected) and not set(range(1, expected + 1)).issubset(known):
        errors.append(f"images must contain contracted slots 1..{expected}")
    delivery = data.get("delivery")
    if isinstance(delivery, dict):
        errors.extend(unknown_errors(delivery,DELIVERY_FIELDS,"delivery"))
        for field in ("docx", "folder", "card"):
            if not isinstance(delivery.get(field), dict): errors.append(f"delivery.{field} must be object")
        if isinstance(delivery.get("docx"),dict):errors.extend(unknown_errors(delivery["docx"],DOCX_FIELDS,"delivery.docx"))
        if isinstance(delivery.get("folder"),dict):errors.extend(unknown_errors(delivery["folder"],FOLDER_FIELDS,"delivery.folder"))
        if isinstance(delivery.get("card"),dict):errors.extend(unknown_errors(delivery["card"],CARD_FIELDS,"delivery.card"))
        if delivery_route == "docx":
            chain=delivery.get("directory_chain")
            if not isinstance(chain,list):errors.append("delivery.directory_chain must be an array")
            else:
                for i,entry in enumerate(chain):
                    if not isinstance(entry,dict):errors.append(f"delivery.directory_chain[{i}] must be object")
                    else:
                        entry_path=f"delivery.directory_chain[{i}]"
                        errors.extend(unknown_errors(entry,DIRECTORY_ENTRY_FIELDS,entry_path))
                        errors.extend(directory_resolution_errors(entry,entry_path))
            token=delivery.get("product_folder_token")
            if token is not None and not isinstance(token,str):errors.append("delivery.product_folder_token must be string or null")
        else:
            for field in ("directory_chain","product_folder_token"):
                if field in delivery:errors.append(f"interactive_card delivery must not contain delivery.{field}")
            if isinstance(delivery.get("docx"),dict):
                for field in ("docx_filename","docx_batch"):
                    if field in delivery["docx"]:errors.append(f"interactive_card delivery must not contain delivery.docx.{field}")
        for field in ("deliverable_slots", "failed_slots"):
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
    try: route_evidence=load(args.delivery_route_file)
    except (OSError,json.JSONDecodeError) as exc: raise ValueError(f"invalid --delivery-route-file: {exc}") from exc
    reject_unknown(route_evidence,{"delivery_route","delivery_route_source","delivery_config_schema_version","delivery_override"},"delivery route")
    route=route_evidence.get("delivery_route");source=route_evidence.get("delivery_route_source");override=route_evidence.get("delivery_override")
    if route not in {"docx","interactive_card"}:raise ValueError("delivery_route must be docx or interactive_card; preview_images is not formal delivery")
    if source not in {"skill_config","bootstrap_result","explicit_user_override"}:raise ValueError("delivery_route_source is not controlled")
    if route_evidence.get("delivery_config_schema_version") != 1:raise ValueError("delivery_config_schema_version must equal 1")
    if source == "explicit_user_override":
        if not isinstance(override,dict) or override.get("delivery_route") != route or not str(override.get("confirmation_text","")).strip() or not is_timezone_datetime(override.get("recorded_at")):raise ValueError("explicit_user_override requires valid delivery_override user evidence")
    elif override is not None:raise ValueError("delivery_override must be null unless source is explicit_user_override")
    slug=None
    if route == "docx":
        missing=[flag for flag,value in (("--agent-name",args.agent_name),("--product-name",args.product_name),("--country-code",args.country_code)) if not isinstance(value,str) or not value.strip()]
        if missing:raise ValueError("docx delivery requires "+", ".join(missing))
        slug=product_slug(args.product_name,args.country_code)
    evidence = policy["override"]
    with manifest_lock(args.manifest):
        path = Path(args.manifest); old_revision, generation = -1, 0
        if path.exists():
            if not args.force: raise ValueError("manifest already exists; use --force")
            old = load(path)
            if not isinstance(old,dict):raise ValueError("existing manifest must be an object")
            if old.get("schema_version") == SCHEMA_VERSION:check_schema(old)
            elif old.get("schema_version") not in {3,4,5,6,7}:raise ValueError("--force can rebuild only schema v3-v7 or current v8 manifest")
            old_revision,generation=old.get("revision"),old.get("generation")
            if not is_int(old_revision) or old_revision<0:raise ValueError("existing revision must be a non-negative integer")
            if not is_int(generation) or generation<1:raise ValueError("existing generation must be a positive integer")
        data = {"schema_version":SCHEMA_VERSION,"manifest_id":str(uuid.uuid4()),"generation":generation+1,"revision":old_revision+1,"created_at":now(),"run_root":str(Path(args.manifest).resolve().parent),
                "task_scope":scope,"plan_mode":args.plan_mode,"expected_count":expected,"confirmed_by_user":bool(scope=="content" or args.confirmed_by_user or args.plan_mode=="default_full"),
                "target_language":target,"docx_language_mode":mode,"localization_policy":policy,"target_only_approval":evidence,"module_contracts":{name:"docx_text" for name in args.requested_module},"requested_docx_modules":list(dict.fromkeys(args.requested_module)),"delivery_route":route,"delivery_route_source":source,"delivery_config_schema_version":1,"delivery_override":override,
                "facts":{"market":args.market,"platform":args.platform,"category":args.category},"modules":{},"images":[slot_shape(n) for n in range(1,expected+1)],
                "tokens":{},
                "delivery":{"deliverable_slots":[],"failed_slots":[],"docx":{"token":None,"permalink":None},"folder":{"permalink":None},"card":{"message_id":None,"send_success":False}},"timings":{},"status":"initialized"}
        if route == "docx":
            data.update(agent_name=args.agent_name.strip(),product_slug=slug,market_country_code=args.country_code.upper(),drive_path_segments=[args.agent_name.strip(),"电商需求","Listing",slug])
            data["delivery"].update(directory_chain=[],product_folder_token=None)
            data["delivery"]["docx"].update(docx_filename=None,docx_batch=None)
        check_schema(data); atomic_save(path,data)


def cmd_slug(args):
    print(product_slug(args.product_name,args.country_code))


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

def permalink_token(value):
    try:return urlparse(value).path.rstrip("/").split("/")[-1]
    except (TypeError,ValueError):return ""


def slot_classification(data):
    contracted = {x["slot"]: x for x in data["images"] if x["slot"] <= data["expected_count"]}
    deliverable, failed = [], []
    for n in range(1, data["expected_count"] + 1):
        status = contracted[n].get("status")
        if status == "success": deliverable.append(n)
        elif status == "failed": failed.append(n)
    return deliverable, failed


def validation_errors(data,delivery=False,manifest_dir=Path.cwd()):
    errors=structural_errors(data)
    if errors:return errors
    scope,expected=data["task_scope"],data["expected_count"]
    if not is_timezone_datetime(data.get("created_at")):errors.append("created_at must be datetime with timezone")
    images=data["images"]; ids={x["slot"] for x in images}
    for x in images:
        n,status=x["slot"],x.get("status")
        if status=="success":
            if x.get("provider_error") is not None:errors.append(f"slot {n}: status success requires provider_error null")
            if escapes_run_root(x.get("file"),data["run_root"]):errors.append(f"slot {n}: delivery file must be contained in run_root (no external absolute, .., or symlink escape)")
            elif not is_readable_regular_file(x.get("file"),data["run_root"]):errors.append(f"slot {n}: delivery file must exist and be a readable regular file")
            elif not has_supported_image_magic(x.get("file"),data["run_root"]):errors.append(f"slot {n}: delivery file must have PNG/JPEG/WebP/GIF magic bytes")
            if data["delivery_route"] == "docx":
                asset=x.get("asset_filename");batch=x.get("image_batch")
                match=re.fullmatch(r"(?:Main|SKU)(\d{3})-(\d{2})\.(png|jpg|jpeg|webp|gif)",asset or "",re.IGNORECASE)
                if not match:errors.append(f"slot {n}: asset_filename must strictly match MainNNN-NN or SKUNNN-NN with a supported image extension")
                elif int(match.group(1))!=n:errors.append(f"slot {n}: asset_filename slot must match current contract slot")
                if not is_int(batch) or batch<1:errors.append(f"slot {n}: image_batch must be a positive integer")
                elif match and int(match.group(2))!=batch:errors.append(f"slot {n}: asset_filename batch must match image_batch")
                actual=resolve_file(x.get("file"),data["run_root"])
                if actual is not None and asset != actual.name:errors.append(f"slot {n}: asset_filename must equal Path(file).name")
        elif status=="failed":
            if x.get("file") is not None:errors.append(f"slot {n}: status failed requires file null")
            if not isinstance(x.get("provider_error"),dict):errors.append(f"slot {n}: status failed requires provider_error")
        elif status!="pending":errors.append(f"slot {n}: unknown status {status!r}")
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
    content_only=scope=="content"
    deliverable,failed=([],[]) if content_only else slot_classification(data)
    if len(deliverable)+len(failed)!=expected:errors.append(f"expected_count={expected} requires every contracted slot to be success or failed")
    extra=[x["slot"] for x in images if x["slot"]>expected]
    if extra:errors.append(f"replacement/extra slots are not part of final delivery: {extra}")
    if state["deliverable_slots"]!=deliverable:errors.append("delivery.deliverable_slots must match successful contracted slots")
    if state["failed_slots"]!=failed:errors.append("delivery.failed_slots must match failed contracted slots")
    timings=data["timings"]; seconds={}
    if not content_only:
        for stage in TIMING_STAGES:
            value=(timings.get(stage) or {}).get("seconds")
            if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<0:errors.append(f"timings.{stage}.seconds must be finite and >= 0")
            else:seconds[stage]=value
        if len(seconds)==4 and any(seconds["total"]<seconds[x] for x in TIMING_STAGES[:-1]):errors.append("timings.total.seconds must be at least each wave")
    tokens=data["tokens"]
    for key in tokens:
        if key not in {str(x) for x in ids}:errors.append(f"unknown token slot {key!r}")
    mode=data["delivery_route"]
    for n in deliverable:
        token=tokens.get(str(n),{})
        if not isinstance(token,dict):errors.append(f"slot {n}: token evidence must be object");continue
        if not is_identifier(token.get("image_key")):errors.append(f"slot {n}: image_key required for {mode} delivery; image_key must be non-whitespace and at least 6 characters")
        if mode=="docx" and not is_identifier(token.get("file_token")):errors.append(f"slot {n}: file_token required for docx delivery; file_token must be non-whitespace and at least 6 characters")
    for n in failed:
        if str(n) in tokens:errors.append(f"slot {n}: failed slot must not have token evidence")
    if mode=="docx":
        docx,folder=state["docx"],state["folder"]
        if not docx.get("token") or not docx.get("permalink"):errors.append("delivery docx token and permalink required")
        elif not is_identifier(docx.get("token")):errors.append("delivery docx token must be non-whitespace and at least 6 characters")
        elif not is_feishu_url(docx.get("permalink")):errors.append("delivery docx permalink must be HTTPS Feishu/Lark URL")
        if not folder.get("permalink"):errors.append("delivery folder permalink required")
        elif not is_feishu_url(folder.get("permalink")):errors.append("delivery folder permalink must be HTTPS Feishu/Lark URL")
        expected_path=[data["agent_name"],"电商需求","Listing",data["product_slug"]]
        if data.get("drive_path_segments") != expected_path:errors.append(f"drive_path_segments must exactly equal {expected_path!r}")
        chain=state.get("directory_chain")
        if not isinstance(chain,list) or len(chain)!=4:errors.append("delivery.directory_chain must contain exactly four folder entries")
        else:
            tokens=[]
            for i,(entry,name) in enumerate(zip(chain,expected_path)):
                path=f"delivery.directory_chain[{i}]"
                if not isinstance(entry,dict):continue
                if entry.get("name")!=name:errors.append(f"{path}.name must be {name!r}")
                if entry.get("type")!="folder":errors.append(f"{path}.type must be folder")
                token=entry.get("token")
                if not isinstance(token,str) or not token.strip() or token.strip().lower() in {"todo","tbd","placeholder","null","none"}:errors.append(f"{path}.token must be non-empty, non-placeholder token")
                else:tokens.append(token)
                parent=entry.get("parent_token")
                if i==0:
                    if parent!="root":errors.append(f"{path}.parent_token must be the literal root sentinel 'root'")
                elif parent!=chain[i-1].get("token"):errors.append(f"{path}.parent_token must equal previous layer token")
                if token and parent==token:errors.append(f"{path} must not self-parent")
            if len(tokens)!=len(set(tokens)):errors.append("delivery.directory_chain tokens must be unique")
            if chain[-1].get("token")!=state.get("product_folder_token"):errors.append("delivery.product_folder_token must equal final directory_chain token")
        folder_token=folder.get("token")
        if folder_token != state.get("product_folder_token"):errors.append("delivery.folder.token must equal product_folder_token")
        if permalink_token(folder.get("permalink")) != state.get("product_folder_token"):errors.append("delivery folder permalink final path segment must equal product_folder_token")
        if permalink_token(docx.get("permalink")) != docx.get("token"):errors.append("delivery docx permalink final path segment must equal docx.token")
        filename,batch=docx.get("docx_filename"),docx.get("docx_batch")
        if not is_int(batch) or batch<1:errors.append("delivery.docx.docx_batch must be a positive integer")
        match=re.fullmatch(r"(\d{8})-(.+)-(\d{3})\.docx",filename or "")
        if not match:errors.append("delivery.docx.docx_filename must match YYYYMMDD-{slug}-{batch:03d}.docx")
        else:
            try:
                filename_date=datetime.strptime(match.group(1),"%Y%m%d").date()
                created=datetime.fromisoformat(data["created_at"].replace("Z","+00:00")).astimezone(timezone.utc).date()
                if filename_date != created:errors.append("delivery.docx.docx_filename date must equal created_at UTC date")
            except (ValueError,KeyError):errors.append("delivery.docx.docx_filename date and created_at must be valid")
            if match.group(2)!=data["product_slug"]:errors.append("delivery.docx.docx_filename slug must match product_slug")
            if is_int(batch) and int(match.group(3))!=batch:errors.append("delivery.docx.docx_filename batch must match docx_batch")
    if content_only:
        if images or data["tokens"] or state["deliverable_slots"] or state["failed_slots"]:errors.append("content scope must not contain image contract or tokens")
        if state["card"].get("send_success") or state["card"].get("message_id"):errors.append("content scope must not require or retain card evidence")
        return errors
    if mode=="interactive_card":
        if any(isinstance(t,dict) and t.get("file_token") for t in tokens.values()) or state["docx"].get("token") or state["docx"].get("permalink") or state["folder"].get("permalink"):errors.append("interactive_card delivery must not retain docx or folder evidence")
    card=state["card"]
    if card.get("send_success") is not True or not is_identifier(card.get("message_id")):errors.append("image delivery requires card send_success true and message_id; message_id must be non-whitespace and at least 6 characters")
    return errors


def cmd_finalize(args):
    def updater(data):
        if data["task_scope"]=="content":data["status"]="ready"
        else:
            deliverable,failed=slot_classification(data)
            data["delivery"]["deliverable_slots"]=deliverable
            data["delivery"]["failed_slots"]=failed
            data["status"]="ready"
        errors=validation_errors(data,True,Path(args.manifest).resolve().parent)
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
    p=sub.add_parser("init");p.add_argument("manifest");p.add_argument("--task-scope",choices=TASK_SCOPES,default="image");p.add_argument("--plan-mode",choices=PLAN_MODES,default="default_full");p.add_argument("--expected-count",type=int);p.add_argument("--confirmed-by-user",action="store_true");p.add_argument("--requested-module",action="append",default=[]);p.add_argument("--delivery-route-file",required=True);p.add_argument("--agent-name");p.add_argument("--product-name");p.add_argument("--country-code");p.add_argument("--market");p.add_argument("--platform");p.add_argument("--category");p.add_argument("--target-language");p.add_argument("--docx-language-mode",choices=LANGUAGE_MODES);p.add_argument("--monolingual",action="store_true");p.add_argument("--monolingual-confirmation");p.add_argument("--target-only-approved-by-user",action="store_true");p.add_argument("--target-only-confirmation");p.add_argument("--force",action="store_true");p.set_defaults(func=cmd_init)
    p=sub.add_parser("slug");p.add_argument("--product-name",required=True);p.add_argument("--country-code",required=True);p.set_defaults(func=cmd_slug)
    for name,func in (("set-facts",cmd_set_facts),("set-image-plan",cmd_set_image_plan),("set-delivery",cmd_set_delivery)):
        p=sub.add_parser(name);add_mutation_args(p);p.set_defaults(func=func)
    p=sub.add_parser("put-module");add_mutation_args(p);p.add_argument("name");p.add_argument("--module-kind",choices=MODULE_KINDS,default="docx_text");p.set_defaults(func=cmd_put_module)
    p=sub.add_parser("update-slot");add_mutation_args(p);p.add_argument("slot",type=json_value);p.set_defaults(func=cmd_update_slot)
    p=sub.add_parser("set-token");add_mutation_args(p);p.add_argument("slot",type=json_value);p.set_defaults(func=cmd_set_token)
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
