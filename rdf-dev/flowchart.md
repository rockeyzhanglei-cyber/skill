# 快开框架（RDF）开发 Skill 流程图

## 整体工作流程

```mermaid
flowchart TB
    subgraph 触发检测
        A[用户输入] --> B{包含关键词?}
        B -->|是| C[触发 rdf-dev Skill]
        B -->|否| D[不触发]
    end

    subgraph 计划阶段["📋 计划阶段 (Step 0-3)"]
        C --> E[Step 0: 需求获取]
        E --> E1{需求来源}
        E1 -->|TFS工作项| E2[获取工作项详情]
        E1 -->|设计图| E3[读取并分析图片]
        E1 -->|用户描述| E4[提取功能点]

        E2 --> F[Step 1: 扫描项目+确认页面]
        E3 --> F
        E4 --> F

        F --> F1[扫描多模块项目]
        F1 --> F2{找到几个项目?}
        F2 -->|1个| F3[简单确认]
        F2 -->|多个| F4[用户选择目标项目]
        F2 -->|0个| F5[提示用户指定路径]

        F3 --> G[Step 2: 生成实施计划]
        F4 --> G
        F5 --> G

        G --> H[Step 3: 用户审核计划]
        H --> I{计划确认?}
        I -->|否| J[修改计划]
        J --> H
    end

    subgraph 执行阶段["🔧 执行阶段 (Step 4-8)"]
        I -->|是| K[Step 4: 创建开发分支]
        K --> K1{选择分支命名}
        K1 -->|"feature/[需求号]"| K2[创建功能开发分支]
        K1 -->|"bugfix/[需求号]"| K3[创建缺陷修复分支]
        K1 -->|手动输入| K4[创建自定义分支]
        K2 --> L[Step 5: 编码实现]
        K3 --> L
        K4 --> L

        L --> L1{识别场景}
        L1 -->|场景A| M1[初始化空白页面]
        L1 -->|场景B| M2[图片生成页面]
        L1 -->|场景C| M3[迭代修改页面]
        L1 -->|场景D| M4[Bug修复]

        M1 --> N[Step 6: 运行项目验证]
        M2 --> N
        M3 --> N
        M4 --> N

        N --> O{验证通过?}
        O -->|否| P[修复问题]
        P --> N

        O -->|是| Q[Step 7: 保存修改记录]
        Q --> R[Step 8: 上传TFS+打标签]
        R --> S[输出工作总结]
    end

    style 计划阶段 fill:#e3f2fd
    style 执行阶段 fill:#e8f5e9
```

---

## Step 1: 多模块项目确认流程（详细）

```mermaid
flowchart TB
    subgraph 扫描项目
        A[开始 Step 1] --> B[扫描快开框架项目]
        B --> B1["find . -path '*/src/mainEntry/xml/pages'"]
        B1 --> C[生成项目列表]
    end

    subgraph 搜索页面
        C --> D{用户指定了 pageCode?}
        D -->|是| E[搜索 pageCode 所在项目]
        D -->|否| F[列出各项目现有页面]

        E --> E1["find . -name '{pageCode}.page.meta.xml'"]
        E1 --> G{找到几个匹配?}
    end

    subgraph 用户确认
        G -->|1个| H[简单确认: 展示唯一结果]
        G -->|多个| I[⚠️ 用户必须选择]
        G -->|0个| J[新建页面: 选择创建位置]

        H --> K[读取项目上下文]
        I --> L[AskUserQuestion 选择]
        J --> M[AskUserQuestion 选择项目]

        L --> K
        M --> K
    end

    subgraph 输出确认
        K --> N[输出目标确认表格]
        N --> O["━━━━━━━━━━━━━━━
        ✅ 目标确认
        - 目标项目: xxx
        - pageCode: xxx
        - 操作场景: xxx
        ━━━━━━━━━━━━━━━"]
        O --> P[进入 Step 2]
    end

    style 用户确认 fill:#fff3e0
    style 输出确认 fill:#e8f5e9
```

---

## Step 5: 编码实现场景流程

### 场景A: 初始化空白页面

```mermaid
flowchart TB
    A[场景A: 初始化空白页面] --> B[获取输入信息]
    B --> B1[项目根目录路径]
    B --> B2[pageCode 页面编码]
    B --> B3[viewCode 默认main]

    B3 --> C[创建目录结构]
    C --> C1["mkdir xml/pages/{pageCode}/"]
    C --> C2["mkdir ctrl/{PageCode}/"]

    C2 --> D[生成页面XML]
    D --> D1[生成 .page.meta.xml]
    D --> D2[生成 .page.layout.xml]

    D2 --> E[生成视图XML]
    E --> E1[生成 .view.xml]
    E --> E2[生成 .layout.xml]

    E2 --> F[生成控制类]
    F --> F1["创建 {PageCode}{ViewCode}Ctrl.ts"]
    F --> F2[注册到 index.ts]

    F2 --> G[执行检查清单]
    G --> H{检查通过?}
    H -->|否| I[修复问题]
    I --> G
    H -->|是| J[完成]
```

---

### 场景B: 图片生成页面

```mermaid
flowchart TB
    A[场景B: 图片生成页面] --> B[读取设计图]
    B --> C[分析图片内容]

    C --> D[识别布局结构]
    D --> D1[上下排列 → FlowVLayout]
    D --> D2[左右排列 → FlowHLayout]
    D --> D3[自由定位 → AbsoluteLayout]
    D --> D4[自动换行 → FlowLayout]

    D --> E[识别组件类型]
    E --> E1[按钮 → Button]
    E --> E2[输入框 → Input]
    E --> E3[表格 → Grid + Dataset]
    E --> E4[表单 → Form + Dataset]
    E --> E5[下拉框 → Select + DataList]

    E --> F{多个输入框相邻?}
    F -->|是| G[合并为 Form 组件]
    F -->|否| H[保持独立组件]

    G --> I[设计数据模型]
    H --> I
    I --> I1[设计 Dataset]
    I --> I2[设计 DataList]

    I2 --> J[生成 .view.xml]
    J --> J1[DataModels 部分]
    J --> J2[Controls 部分]
    J --> J3[Events 部分]

    J3 --> K[生成 .layout.xml]
    K --> K1[布局结构]
    K --> K2[Panel 容器]
    K --> K3[组件位置/尺寸]

    K3 --> L[生成控制类]
    L --> L1[解析 Events]
    L --> L2[生成事件方法]
    L --> L3[注册到 index.ts]

    L3 --> M[执行检查清单]
    M --> N{验证绑定正确?}
    N -->|否| O[添加绑定]
    O --> M
    N -->|是| P[完成]
```

---

### 场景C: 迭代修改页面

```mermaid
flowchart TB
    A[场景C: 迭代修改页面] --> B[分析需求变更]
    B --> B1[新增组件?]
    B --> B2[修改属性?]
    B --> B3[调整布局?]
    B --> B4[新增事件?]
    B --> B5[修改数据模型?]

    B1 --> C[定位目标文件]
    C --> C1[".view.xml 组件定义"]
    C --> C2[".layout.xml 布局结构"]
    C --> C3["控制类 .ts"]

    C3 --> D[评估修改影响]
    D --> D1[是否影响现有组件?]
    D --> D2[是否需要新增数据模型?]
    D --> D3[是否需要新增事件方法?]

    D3 --> E{修改类型}

    E -->|新增组件| F1[修改 .view.xml + .layout.xml]
    E -->|修改属性| F2[修改 .view.xml]
    E -->|调整布局| F3[修改 .layout.xml]
    E -->|新增事件| F4[修改 .view.xml + 控制类]
    E -->|修改数据模型| F5[修改 .view.xml]

    F1 --> G[验证兼容性]
    F2 --> G
    F3 --> G
    F4 --> G
    F5 --> G

    G --> G1[现有功能正常?]
    G1 -->|否| H[回滚修改]
    G1 -->|是| G2[组件 ID 一致?]
    G2 -->|否| I[修复 ID]
    G2 -->|是| J[完成]
    H --> K[重新评估方案]
    I --> G
```

---

### 场景D: Bug 修复

```mermaid
flowchart TB
    A[场景D: Bug 修复] --> B[接收问题描述]
    B --> B1[组件不显示]
    B --> B2[事件不响应]
    B --> B3[表格无数据]
    B --> B4[表单无法输入]
    B --> B5[下拉框无选项]

    B1 --> C1{排查组件不显示}
    C1 --> C1a[布局有 Panel?]
    C1a -->|否| D1[添加 Panel]
    C1a -->|是| C1b[组件绑定数据模型?]
    C1b -->|否| D2[添加绑定]
    C1b -->|是| C1c[visible=true?]
    C1c -->|否| D3[修改 visible]

    B2 --> C2{排查事件不响应}
    C2 --> C2a[控制类已注册?]
    C2a -->|否| D4[注册到 index.ts]
    C2a -->|是| C2b[方法命名正确?]
    C2b -->|否| D5[修正方法名]
    C2b -->|是| C2c[事件参数类型正确?]
    C2c -->|否| D6[修正参数类型]

    B3 --> C3{排查表格无数据}
    C3 --> C3a[Dataset 已绑定?]
    C3a -->|否| D7[绑定 Dataset]
    C3a -->|是| C3b[Dataset 有 Fields?]
    C3b -->|否| D8[添加 Fields]

    B4 --> C4{排查表单无法输入}
    C4 --> C4a[Dataset isEdit=true?]
    C4a -->|否| D9[设置 isEdit=true]

    B5 --> C5{排查下拉框无选项}
    C5 --> C5a[DataList 已绑定?]
    C5a -->|否| D10[绑定 DataList]
    C5a -->|是| C5b[DataList 有 DataItem?]
    C5b -->|否| D11[添加 DataItem]

    D1 --> E[验证修复]
    D2 --> E
    D3 --> E
    D4 --> E
    D5 --> E
    D6 --> E
    D7 --> E
    D8 --> E
    D9 --> E
    D10 --> E
    D11 --> E

    E --> F{问题解决?}
    F -->|是| G[完成修复]
    F -->|否| H[继续排查]
    H --> I[请求更多信息]
```

---

## 检查点流程

```mermaid
flowchart LR
    subgraph 计划阶段检查
        A1[需求来源已确认]
        A2[TFS 工作项已获取]
        A3[附件已下载]
        A4[**已扫描多模块项目**]
        A5[**已确认目标项目**]
        A6[**用户确认目标页面**]
        A7[生成实施计划]
        A8[用户确认计划]
    end

    subgraph 执行阶段检查
        B1[Git 状态检查]
        B2["分支命名规范(feature/bugfix/自定义)"]
        B3[文件路径正确]
        B4[pageCode 大小写一致]
        B5[Dataset/DataList 绑定]
        B6[组件 ID 一致]
        B7[布局 Panel 正确]
        B8[控制类已注册]
        B9[事件方法命名规范]
    end

    subgraph 验证阶段检查
        C1[运行项目]
        C2[页面加载正常]
        C3[组件渲染正常]
        C4[事件响应正常]
        C5[保存修改记录]
        C6[上传 TFS]
    end

    A1 --> A2 --> A3 --> A4 --> A5 --> A6 --> A7 --> A8
    A8 --> B1 --> B2 --> B3 --> B4 --> B5 --> B6 --> B7 --> B8 --> B9
    B9 --> C1 --> C2 --> C3 --> C4 --> C5 --> C6

    style A4 fill:#ffeb3b
    style A5 fill:#ffeb3b
    style A6 fill:#ffeb3b
```

---

## 文件关系图

```mermaid
graph LR
    subgraph 页面XML["📄 页面级 XML"]
        A1[".page.meta.xml<br/>页面配置"] --> A2[".page.layout.xml<br/>页面布局"]
    end

    subgraph 视图XML["📄 视图级 XML"]
        B1[".view.xml<br/>组件定义"] --> B2[".layout.xml<br/>布局结构"]
        B1 -->|定义事件| C1["控制类.ts<br/>业务逻辑"]
    end

    subgraph 控制类["📝 控制类"]
        C1 -->|注册| C2["index.ts<br/>导出配置"]
        C1 -->|自定义渲染| C3["Render.tsx<br/>渲染组件"]
    end

    A1 -->|引用视图| B1
    A2 -->|引用视图| B2

    style 页面XML fill:#e1f5fe
    style 视图XML fill:#f3e5f5
    style 控制类 fill:#e8f5e9
```

---

## 目录结构

```
{项目根目录}/
├── src/mainEntry/
│   ├── xml/pages/{pageCode}/
│   │   ├── {pageCode}.page.meta.xml      # 页面配置
│   │   ├── {pageCode}.page.layout.xml    # 页面布局
│   │   ├── {pageCode}.{viewCode}.view.xml    # 视图定义
│   │   └── {pageCode}.{viewCode}.layout.xml  # 视图布局
│   └── ctrl/{PageCode}/
│       ├── {PageCode}{ViewCode}Ctrl.ts   # 控制类
│       ├── {PageCode}Render.tsx          # 渲染组件（可选）
│       └── index.ts                      # 注册导出
├── docs/
│   ├── plans/
│   │   └── yyyy-mm-dd-需求号.md          # 实施计划
│   └── feature/
│       ├── yyyy-mm-dd-需求号.md          # 修改记录
│       └── AI-CODING-log-yyyy-mm-dd.txt     # 对话导出
└── product-docs/
    └── {需求号}/                         # 需求文档
        ├── 设计图.png
        └── 需求说明.docx
```

---

## 多模块项目示例

```
工作目录/
├── wn-his-web/                    # HIS 系统
│   ├── src/mainEntry/
│   │   ├── xml/pages/
│   │   │   ├── userManage/        # 用户管理页面
│   │   │   └── patientQuery/      # 患者查询页面
│   │   └── ctrl/
│   ├── .sparkrc.ts
│   └── package.json
│
├── wn-emr-web/                    # EMR 系统
│   ├── src/mainEntry/
│   │   ├── xml/pages/
│   │   │   ├── userManage/        # 用户管理页面（同名）
│   │   │   └── emrEditor/         # 病历编辑页面
│   │   └── ctrl/
│   ├── .sparkrc.ts
│   └── package.json
│
└── wn-lis-web/                    # LIS 系统
    ├── src/mainEntry/
    │   ├── xml/pages/
    │   │   └── sampleManage/      # 样本管理页面
    │   └── ctrl/
    ├── .sparkrc.ts
    └── package.json
```

**⚠️ 注意**: 当 `userManage` 在多个项目中存在时，Step 1 会要求用户确认目标项目。

---

## 触发关键词

| 类别 | 关键词 |
|-----|-------|
| 框架名称 | 快开框架、RDF、rdf、pango-framework |
| 编码标识 | pageCode、viewCode |
| 文件类型 | .page.meta.xml、.view.xml、.layout.xml |
| 操作动词 | 生成页面、创建页面、初始化页面、开发需求 |
| 修改动词 | 修改组件、调整布局、添加事件 |
| 问题关键词 | 组件不显示、事件不响应、表格无数据 |

---

## 常见问题排查表

| 现象 | 可能原因 | 排查步骤 | 解决方案 |
|-----|---------|---------|---------|
| 组件不显示 | 布局缺少 Panel | 检查 .layout.xml | 添加 FlowVPanel/FlowHPanel |
| 组件不显示 | 组件未绑定数据模型 | 检查 dataset/datalist 属性 | 添加数据模型绑定 |
| 组件不显示 | visible=false | 检查 visible 属性 | 设置 visible="true" |
| 事件不响应 | 控制类未注册 | 检查 index.ts | 添加注册 |
| 事件不响应 | 方法命名错误 | 检查方法名格式 | 使用 组件ID+事件名 格式 |
| 事件不响应 | 事件参数类型错误 | 检查泛型参数 | 使用正确的事件类型 |
| 表格无数据 | Dataset 未绑定 | 检查 Grid 的 dataset 属性 | 绑定 Dataset |
| 表格无数据 | Dataset 无 Fields | 检查 Fields 定义 | 添加 Field 元素 |
| 表单无法输入 | Dataset isEdit=false | 检查 Dataset 的 isEdit | 设置 isEdit="true" |
| 下拉框无选项 | DataList 未绑定 | 检查 Select 的 datalist 属性 | 绑定 DataList |
| 下拉框无选项 | DataList 无 DataItem | 检查 DataItem 定义 | 添加 DataItem 元素 |
