# 通用语义匹配引擎（详细技术方案）

> 本文档从 SKILL.md 外置，含完整的知识库定义与匹配函数实现。
> **可执行完整实现见** `references/semantic-match-engine.py`（V8 最终版，可直接复用）。

### 通用语义匹配引擎

#### 适用场景
将区域标准规范与省平台/国家平台标准规范进行比对，按"只增不减不更名"原则修订。

#### 核心算法

```
省字段名 → normalize → 同义词替换 → 去后缀(TECH_SUFFIXES) → core
医字段名 → normalize → 同义词替换 → 去后缀(TECH_SUFFIXES) → core
                       ↓
          比较core（精确 > 同义词核心 > 同义包含≥30% > 同义词全名）
```

#### 关键规则

**跨类别禁止**：代码/编码类 ≠ 名称/日期/金额/标志类（同核心例外）
**包含比限制**：被包含部分/总长度 ≥ 30% 才接受
**短核心兜底**：核心≤3字时回退到同义词全名匹配

#### 可复用的知识库

| 组件 | 说明 |
|------|------|
| TECH_SUFFIXES(技术后缀) | 约60个，所有文档通用 |
| SYNONYM(同义词) | 约500对，医疗行业通用 |
| BLOCK_LIST(阻塞列表) | 少量字段特定，每个文档需过一遍 |

#### 技术后缀列表

```python
TECH_SUFFIXES = [
    '代码','名称','编码','标志','标识','类别','号码','编号','日期','时间',
    '金额','费用','类型','方式','途径','级别','描述','原因','说明','单位',
    '情况','来源','标准','分类','格式','数据','信息','记录','明细','结果',
    '报告','项目','指标','参数','值域','范围','流水号','状态','编码','规格',
    '品级','归类','密码','账号','途径','工号','编号','性质','特征','操作','姓名'
]
```

#### 同义词示例

```python
SYNONYM = {
    '患者':'病人','病人':'患者','院区':'分院','分院':'院区',
    '社保卡':'医保卡','医保卡':'社保卡','预约':'挂号','挂号':'预约',
    '就诊':'诊疗','诊疗':'就诊','门诊':'门急诊','门急诊':'门诊',
    '就诊状态':'是否就诊','是否就诊':'就诊状态',
    '是否专家':'专家号','专家号':'是否专家',
    '科室':'科室代码','科室代码':'科室','费用':'金额','金额':'费用',
    '诊察费':'挂号费','挂号费':'诊察费','个人支付':'自付','自付':'个人支付',
    '身份证号':'证件号码','证件号码':'身份证号',
    '身份证件':'证件','证件':'身份证件','身份证':'证件',
    '联系电话':'电话','电话':'联系电话','手机':'手机号','手机号':'手机',
    '预约途径':'挂号途径','挂号途径':'预约途径',
    '出生地':'出生地','工作单位电话':'电话',
    '医疗费用支付方式':'支付方式','支付方式':'医疗费用支付方式',
    '医保':'医保','个人医保账户':'个人支付','个人支付':'个人医保账户',
    '院内科室':'科室','平台科室':'科室','病人性别':'性别','性别':'病人性别',
    '新生儿出生体重':'新生儿体重','住院天数':'住院天数','住院日':'住院天数',
    '住院次数':'入院次数','入院次数':'住院次数','住院':'住院','入院':'住院',
    '出院':'出院','修改标志':'修改','数据状态':'修改',
    '预约挂号':'预约','预约挂号标识':'预约','退号标志':'退号','退号':'退号标志',
    '是否急诊':'急诊','急诊':'是否急诊','是否急诊挂号':'急诊',
    '挂号操作员':'操作员','操作员':'挂号操作员',
    '是否专家号':'专家','专家':'是否专家号',
    # ... 完整版见skill references/semantic-match-engine.py
}
```

#### 语义类别判断

```python
def sem_cat(name):
    """判断字段语义类别"""
    if name.endswith(('代码','编码','工号','号码')): return 'code'
    if name.endswith(('名称','名字')): return 'name'
    if name.endswith(('日期','时间')): return 'date'
    if name.endswith(('金额','费用','费')): return 'amount'
    if name.endswith(('标志','标识')): return 'flag'
    return 'other'
```

#### 匹配函数

```python
def match(prov_name, yn_name):
    """语义匹配，返回(score, reason)"""
    p = core(prov_name)  # normalize + 同义词 + 去后缀
    y = core(yn_name)
    
    # 1. 跨类别禁止
    pc, yc = sem_cat(prov_name), sem_cat(yn_name)
    # 代码类 ≠ 名称/日期/金额/描述/级别/状态/单位
    if pc == 'code' and yc in ('name','date','amount','desc','level','status','unit'):
        if p == y: return 95, '跨类别同核心'
        return 0, '跨类别'
    # 名称类 ≠ 代码/编码
    if pc == 'name' and yc == 'code':
        if p == y: return 95, '跨类别同核心'
        return 0, '跨类别'
    # 日期类 ≠ 代码/编码
    if pc == 'date' and yc == 'code': return 0, '跨类别'
    # 金额类 ≠ 代码/编码/标志
    if pc == 'amount' and yc in ('code','flag'): return 0, '跨类别'
    # 标志类 ≠ 金额
    if pc == 'flag' and yc == 'amount': return 0, '跨类别'
    
    # 2. 同义词核心匹配
    ps = synonyms(p); ys = synonyms(y)
    for sp in ps:
        for sy in ys:
            if sp == sy: return 90, f'同义词核心:{sp}'
            # 包含关系（双方核心≥3字）
            if len(sp) >= 3 and len(sy) >= 3:
                if sp in sy or sy in sp:
                    ratio = len(min(sp,sy,key=len))/len(max(sp,sy,key=len))
                    if ratio >= 0.3: return 80, f'同义包含(比{ratio:.0%})'
    
    # 3. 同义词全名匹配（无后缀剥离）
    pn = syn_full(prov_name); yn = syn_full(yn_name)
    if pn == yn: return 85, '同义词全名匹配'
    if pn in yn or yn in pn:
        ratio = len(min(pn,yn,key=len))/len(max(pn,yn,key=len))
        if ratio >= 0.3: return 75, f'同义词全名包含(比{ratio:.0%})'
    
    return 0, ''
```

---

## 与实现文件的对应关系

| 本文段落 | 实现文件位置 |
|----------|-------------|
| 核心算法（normalize→同义词→去后缀→core） | `semantic-match-engine.py` 顶部 docstring |
| 技术后缀列表（约60个） | `TECH_SUFFIXES` |
| 同义词库（约500对，本文为示例） | `SYNONYM`（完整版） |
| 语义类别判断 `sem_cat` | `semantic-match-engine.py` 内同名函数 |
| 匹配函数 `match` | `semantic-match-engine.py` 内同名函数 |

**注意**：本文的代码示例为精简版（同义词仅列示例），**实际使用时以 `semantic-match-engine.py` 为准**。
