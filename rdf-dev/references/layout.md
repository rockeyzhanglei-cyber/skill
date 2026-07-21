# 布局组件参考

## 布局分类

| 布局类型 | XML标签 | 用途 | 子元素规则 |
|----------|---------|------|------------|
| 纵向布局 | FlowVLayout | 垂直排列 | 必须包含FlowVPanel |
| 横向布局 | FlowHLayout | 水平排列 | 必须包含FlowHPanel |
| 绝对布局 | AbsoluteLayout | 自由定位 | 可直接放置多个组件 |
| 流式布局 | FlowLayout | 自动排列 | 可直接放置多个组件 |
| 页签布局 | TabLayout | 页签切换 | TabPanel |
| 卡片布局 | CardLayout | 卡片堆叠 | CardPanel |
| 分割布局 | SplitterLayout | 分割区域 | SplitterOne, SplitterTwo |
| 折叠布局 | AccordionLayout | 折叠展开 | AccordionPanel |

## 布局规则

1. **FlowVLayout/FlowHLayout**：必须使用 Panel，Panel 内只能放一个组件或布局
2. **AbsoluteLayout/FlowLayout**：可直接放多个组件，不能放布局
3. **首次生成空白页面**：视图下可以不放布局，直接创建空的 `<View>` 根节点

## FlowVLayout（纵向布局）

```xml
<FlowVLayout id="mainLayout" visible="true" height="100%">
    <FlowVPanel id="panel1" visible="true">
        <Button id="btn1" width="88" height="32"/>
    </FlowVPanel>
    <FlowVPanel id="panel2" visible="true">
        <Grid id="grid1"/>
    </FlowVPanel>
</FlowVLayout>
```

## FlowHLayout（横向布局）

```xml
<FlowHLayout id="buttonLayout" visible="true">
    <FlowHPanel id="panel1" visible="true" width="88">
        <Button id="btn1" width="88" height="32"/>
    </FlowHPanel>
    <FlowHPanel id="panel2" visible="true" width="88">
        <Button id="btn2" width="88" height="32"/>
    </FlowHPanel>
</FlowHLayout>
```

## AbsoluteLayout（绝对布局）

```xml
<AbsoluteLayout id="absoluteLayout" visible="true" height="100%">
    <Button id="btn1" width="88" height="32" top="10" left="25" position="absolute"/>
    <Input id="input1" width="200" height="32" top="50" left="25" position="absolute"/>
</AbsoluteLayout>
```

## 布局选择指南

| 场景 | 推荐布局 | 说明 |
|------|----------|------|
| 上下排列内容 | FlowVLayout | 每个 Panel 一个组件 |
| 左右排列内容 | FlowHLayout | 每个 Panel 一个组件 |
| 精确位置控制 | AbsoluteLayout | 通过 top/left 定位 |
| 自动换行排列 | FlowLayout | 自动排列 |
| 多页面切换 | TabLayout | 页签切换 |
| 可调整分割 | SplitterLayout | 主副区域分割 |
| 折叠内容 | AccordionLayout | 折叠展开 |

## 布局属性

| 属性名 | 描述 | 类型 | 适用布局 |
|--------|------|------|----------|
| id | 唯一标识 | string | 全部 |
| visible | 是否可见 | boolean | 全部 |
| height | 高度 | number/string | FlowVLayout, AbsoluteLayout |
| width | 宽度 | number | FlowHLayout |
| cssStyle | 自定义样式 | string | 全部 |
| isAutoFill | 自动填充 | boolean | FlowHLayout, FlowVLayout |

## 常用布局组合

```xml
<!-- 典型的页面布局：纵向主布局 + 横向按钮行 -->
<FlowVLayout id="mainLayout" height="100%">
    <!-- 按钮行 -->
    <FlowVPanel id="buttonPanel" height="40">
        <FlowHLayout id="buttonLayout">
            <FlowHPanel id="btnPanel1" width="88">
                <Button id="btn1" width="88" height="32"/>
            </FlowHPanel>
            <FlowHPanel id="btnPanel2" width="88">
                <Button id="btn2" width="88" height="32"/>
            </FlowHPanel>
        </FlowHLayout>
    </FlowVPanel>
    <!-- 内容区域 -->
    <FlowVPanel id="contentPanel">
        <Grid id="dataGrid"/>
    </FlowVPanel>
</FlowVLayout>
```
