# -*- coding: utf-8 -*-
"""诊断特定字段为什么没匹配上（调试用）"""
import sys, os, json

SKILL_DIR = '/Users/zhanglei/.cache/WinCode/skill/data-model-compare'
sys.path.insert(0, SKILL_DIR)

from parsers.standard_parser import StandardDocument, StandardTable, StandardField, ValueDomain
from matchers.standard_comparator import StandardComparator
import yaml

# ===== 1. 从缓存 JSON 加载两份标准 =====
def load_doc(path):
    with open(path) as f:
        data = json.load(f)
    tables = []
    for t in data['tables']:
        fields = []
        for fl in t.get('fields', []):
            vds = []
            for vd in (fl.get('value_domains') or []):
                vds.append(ValueDomain(code=vd.get('code',''), name=vd.get('name','')))
            fields.append(StandardField(
                name=fl.get('name',''),
                chinese_name=fl.get('chinese_name',''),
                data_type=fl.get('data_type',''),
                length=fl.get('length',0),
                constraint=fl.get('constraint',''),
                description=fl.get('description',''),
                value_domains=vds,
                data_element_id=fl.get('data_element_id',''),
                format=fl.get('format',''),
            ))
        tables.append(StandardTable(
            name=t.get('name',''),
            chinese_name=t.get('chinese_name',''),
            description=t.get('description',''),
            fields=fields,
        ))
    return StandardDocument(source_file=data.get('source_file',''), tables=tables, metadata=data.get('metadata',{}))

TEMP = '/Users/zhanglei/data-model-compare-docs/新疆自治区标准_vs_乌鲁木齐标准/temp'
src_doc = load_doc(os.path.join(TEMP, 'source_standard.json'))
tgt_doc = load_doc(os.path.join(TEMP, 'target_standard.json'))

# ===== 2. 构建比对器（与 main.py 相同配置） =====
with open(os.path.join(SKILL_DIR, 'config.yaml')) as f:
    config = yaml.safe_load(f)
comparator_config = {
    'field_matching': config.get('field_matching', {}),
    'constraint_protection': config.get('constraint_protection', {}),
    'length_protection': config.get('length_protection', {}),
    'value_domain_matching': config.get('value_domain_matching', {}),
    'cross_table_relation': config.get('cross_table_relation', {}),
}
cmp_ = StandardComparator(comparator_config)
cmp_._build_auto_relations(src_doc)

# ===== 3. 找到目标表 BASEINFO 和源表 JBBRJBXXB =====
target_table = next(t for t in tgt_doc.tables if t.name == 'BASEINFO')
source_table = next(t for t in src_doc.tables if t.name == 'JBBRJBXXB')
print(f'目标表: {target_table.name} {target_table.chinese_name} ({len(target_table.fields)}字段)')
print(f'源表:   {source_table.name} {source_table.chinese_name} ({len(source_table.fields)}字段)')

source_table_index = {t.name: t for t in src_doc.tables}
for t in src_doc.tables:
    if t.chinese_name:
        source_table_index[t.chinese_name] = t
    source_table_index[f"{t.name}|{t.chinese_name}"] = t
source_field_index = {f.name: f for f in source_table.fields}

# ===== 4. 对目标字段逐通道诊断 =====
target_fields = ['PATIENT_ID', 'ID_NO', 'ABO_CODE', 'RH_CODE']
for tf_name in target_fields:
    tf = next(f for f in target_table.fields if f.name == tf_name)
    print('\n' + '='*70)
    print(f'目标字段: {tf.name} | {tf.chinese_name} | 类型={tf.data_type} len={tf.length} | 说明: {tf.description[:50]}')
    print('='*70)

    # --- 4.1 精确中文（本表内） ---
    hit = None
    for sf in source_field_index.values():
        if tf.chinese_name and tf.chinese_name == sf.chinese_name:
            hit = sf
            break
    print(f'[exact_chinese-本表] {"命中: " + hit.name if hit else "未命中"}')

    # --- 4.2 精确英文 ---
    hit = source_field_index.get(tf.name)
    # 大小写敏感
    print(f'[exact_english] {"命中: " + hit.name if hit else "未命中"}')

    # --- 4.3 同义词 ---
    print('[synonym 通道]')
    syn_hits = []
    for sf in source_field_index.values():
        try:
            ok = cmp_._is_synonym_match(tf.chinese_name, sf.chinese_name)
        except Exception as e:
            ok = False
        if ok:
            syn_hits.append(sf)
    # 兼容性检查
    for sf in syn_hits:
        desc_ok = cmp_._is_description_compatible(tf, sf)
        print(f'  - 同义命中: {sf.name} | {sf.chinese_name} | 描述兼容={desc_ok}')
    if not syn_hits:
        print('  - 无同义命中')

    # --- 4.4 语义 ---
    print('[semantic 通道]')
    sem_hits = []
    for sf in source_field_index.values():
        try:
            ok = cmp_._is_semantic_match(tf.chinese_name, sf.chinese_name)
        except Exception as e:
            ok = False
        if ok:
            sem_hits.append((sf, _calculate_sim(tf.chinese_name, sf.chinese_name)))
    for sf, sim in sem_hits:
        print(f'  - 语义命中: {sf.name} | {sf.chinese_name} | 相似度={sim:.3f}')
    if not sem_hits:
        print('  - 无语义命中（相似度不足或网关拦截）')

    # --- 4.5 关键词 ---
    print('[keyword 通道]')
    kw_hits = []
    for sf in source_field_index.values():
        try:
            ok1 = cmp_._is_keyword_match(tf.chinese_name, sf.chinese_name)
            ok2 = cmp_._is_type_compatible_for_keyword(tf, sf) if hasattr(cmp_, '_is_type_compatible_for_keyword') else True
            ok3 = cmp_._is_code_name_compatible(tf.chinese_name, sf.chinese_name) if hasattr(cmp_, '_is_code_name_compatible') else True
            ok4 = cmp_._is_description_compatible(tf, sf)
        except Exception as e:
            ok1 = ok2 = ok3 = ok4 = False
        if ok1 and ok2 and ok3 and ok4:
            kw_hits.append(sf)
    for sf in kw_hits:
        print(f'  - 关键词命中: {sf.name} | {sf.chinese_name}')
    if not kw_hits:
        print('  - 无关键词命中')

    # --- 4.6 逐候选源字段分析：为什么 YYDAH/ZJHM/RHXXDM/ABOXXDM 没被命中 ---
    print('[关键候选源字段逐项分析]')
    for cand in ['YYDAH', 'ZJHM', 'ABOXXDM', 'RHXXDM']:
        sf = source_field_index.get(cand)
        if not sf:
            continue
        syn_ok = cmp_._is_synonym_match(tf.chinese_name, sf.chinese_name)
        sem_ok = cmp_._is_semantic_match(tf.chinese_name, sf.chinese_name)
        kw_ok = cmp_._is_keyword_match(tf.chinese_name, sf.chinese_name)
        desc_ok = cmp_._is_description_compatible(tf, sf)
        # 如果 synonym False，给出细节
        detail = ''
        if not syn_ok and tf.chinese_name and sf.chinese_name:
            role_ok = cmp_._is_role_compatible_for_synonym(tf.chinese_name, sf.chinese_name)
            concept_ok = cmp_._is_concept_compatible_for_synonym(tf.chinese_name, sf.chinese_name)
            core_ok = cmp_._core_concept_compatible(tf.chinese_name, sf.chinese_name)
            kind_ok = cmp_._field_kind_compatible(tf.chinese_name, sf.chinese_name)
            detail = f' role={role_ok} concept={concept_ok} core={core_ok} kind={kind_ok}'
        print(f'  {cand} {sf.chinese_name}: synonym={syn_ok}{detail} semantic={sem_ok} keyword={kw_ok} desc={desc_ok}')

def _calculate_sim(a, b):
    from matchers.standard_comparator import _calculate_similarity
    return _calculate_similarity(a.replace(' ',''), b.replace(' ',''))