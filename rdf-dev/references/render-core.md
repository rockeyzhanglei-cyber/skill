# RDF 框架自定义渲染说明

## 概述

当快开框架提供的组件无法满足业务需求时，可以使用自定义渲染机制。自定义渲染支持使用 **win-design-next** 组件库来构建更丰富的 UI 界面。

## 支持的场景

1. 布局 panel 自定义渲染（FlowHPanel、FlowVPanel）
2. 表格列自定义渲染

## win-design-next 组件库

### 使用规则

1. **组件标签必须以 `<W` 开头（大写）**，如 `<WButton>`、`<WInput>` 等
2. **需要手动导入组件**：`import { WButton } from 'win-design-next';`
3. **禁止使用 React hooks**：自定义渲染方法中不能使用 `useState`、`useEffect` 等
4. **使用类属性管理状态**：通过 `this.xxx` 访问和修改状态
5. **禁止使用其他 UI 组件库**：如 Element Plus、Ant Design 等

### 快速开始

```tsx
import { WButton, WInput } from 'win-design-next';

myCustomRender(yPanel, yView) {
    return (
        <div>
            <WButton type="primary" onClick={() => { this.handleClick(); }}>
                点击我
            </WButton>
            <WInput
                value={this.inputValue}
                onChange={(val) => { this.inputValue = val; }}
            />
        </div>
    );
}
```

## 自定义渲染实现方式

### 1. 布局 panel 自定义渲染

#### XML 部分（layout.xml）
- `controller` 指定自定义渲染类
- `render` 指定自定义渲染方法，必须返回一个标签节点

```xml
<FlowHLayout id="flowhlayout7755" className="designerTopLayout">
    <FlowHPanel id="panel1" width="192" controller="designer/container/ContainerPage" render="toggleProjectRender"/>
</FlowHLayout>
```

#### TSX 部分
参数说明:
- `yPanel`: 自定义渲染的 panel 实例
- `yView`: 自定义渲染的 panel 所在的 yView 实例

```tsx
toggleProjectRender(yPanel, yView) {
    return (
        <div>
            <span>项目</span>
        </div>
    );
}
```

### 2. 表格列自定义渲染

#### XML 部分（view.xml）
- `renderType`: 等于`CustomRender`
- `customRender`: 指定自定义渲染方法
- `controller`: 指定自定义渲染类

```xml
<Grid id="grid1" dataset="listDs">
    <GridColumn id="operation" field="operation" text="操作" renderType="CustomRender" customRender="operationRender" controller="mainEntry/ctrl/Page/PageRender"/>
</Grid>
```

#### TSX 部分
参数说明:
- `text`: 表格列文本
- `record`: 表格行数据
- `index`: 表格行索引
- `field`: 表格列字段
- `column`: 表格列实例
- `row`: 表格行实例

```tsx
import { WButton } from 'win-design-next';

operationRender(text, record, index, field, column, row) {
    return (
        <div style={{ display: 'flex', gap: '8px' }}>
            <WButton type="primary" size="small" onClick={() => { this.handleEdit(row); }}>
                编辑
            </WButton>
            <WButton type="danger" size="small" onClick={() => { this.handleDelete(row); }}>
                删除
            </WButton>
        </div>
    );
}
```

## 注意事项

### 状态管理

自定义渲染方法中**禁止使用 React hooks**，应使用类属性来管理状态：

```tsx
// ✅ 正确：使用类属性
myRender(yPanel, yView) {
    return (
        <WInput
            value={this.inputValue}
            onChange={(val) => { this.inputValue = val; }}
        />
    );
}

// ❌ 错误：不能使用 React hooks
```

### 组件导入

必须手动导入 win-design-next 组件：

```tsx
// ✅ 正确
import { WButton, WInput } from 'win-design-next';

// ❌ 错误：组件不会自动注册
```

### 组件标签命名

win-design-next 组件标签必须以 `<W` 开头（大写）：

```tsx
// ✅ 正确
<WButton>按钮</WButton>

// ❌ 错误
<Button>按钮</Button>
```

## 常用 win-design-next 组件

| 组件 | 标签 | 用途 |
|-----|------|------|
| 按钮 | WButton | 操作按钮 |
| 输入框 | WInput | 文本输入 |
| 下拉框 | WSelect | 下拉选择 |
| 表格 | WTable | 数据表格 |
| 对话框 | WModal | 弹出对话框 |
| 抽屉 | WDrawer | 侧边抽屉 |
| 下拉菜单 | WDropdown | 下拉菜单 |
| 消息提示 | WMessage | 消息提示 |
