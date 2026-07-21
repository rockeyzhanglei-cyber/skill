# RDF 框架前端项目目录结构说明

## 整体结构
```
src/
├── img/              # 图片资源
├── mainEntry/        # 主入口模块
│   ├── ctrl/         # 控制类目录
│   └── xml/          # 页面XML文件
├── CtrlContext.ts    # 控制类上下文
└── main.ts           # 项目入口文件
```

## 目录说明

### img/
存放项目中使用的图片资源。

### mainEntry/
项目主入口模块，包含控制器和页面配置。

#### ctrl/
各页面（PageCode）的控制类实现，按功能页面划分目录：
- 示例：`AutomaticEnrollment/`、`CaseInformationManagement/`

每个页面目录包含：
- `{PageCode}{ViewCode}Ctrl.ts`：视图控制类，一个视图对应一个控制类（强制）
- `{PageCode}Render.tsx`：自定义渲染控制类（可选）
- `index.ts`：控制类注册文件

#### xml/
页面配置文件，采用XML格式定义页面结构和元数据：
- `pages/`：按页面功能划分的页面配置
- `pages/{PageCode}/{PageCode}.page.meta.xml`：页面元配置
- `pages/{PageCode}/{PageCode}.page.layout.xml`：页面布局配置
- `pages/{PageCode}/{PageCode}.{ViewCode}.view.xml`：视图配置
- `pages/{PageCode}/{PageCode}.{ViewCode}.layout.xml`：视图布局配置

### CtrlContext.ts
控制器上下文，管理控制器实例和状态。

### main.ts
项目入口文件，启动Vue应用。

## 文件生成位置规则

### XML 文件
```
src/mainEntry/xml/pages/{pageCode}/
├── {pageCode}.page.meta.xml      # 页面元配置
├── {pageCode}.page.layout.xml    # 页面布局配置
├── {pageCode}.{viewCode}.view.xml    # 视图组件配置
└── {pageCode}.{viewCode}.layout.xml  # 视图布局配置
```

### 控制类文件
```
src/mainEntry/ctrl/{PageCode}/
├── {PageCode}{ViewCode}Ctrl.ts   # 一般控制类（强制）
├── {PageCode}Render.tsx          # 渲染控制类（可选）
└── index.ts                      # 注册文件
```

## 注册示例

```typescript
// src/mainEntry/ctrl/index.ts
import {PageCode}{ViewCode}Ctrl from "./{PageCode}/{PageCode}{ViewCode}Ctrl";
import {PageCode}Render from "./{PageCode}/{PageCode}Render";

export default {
    {PageCode}{ViewCode}Ctrl,
    {PageCode}Render,
};
```
