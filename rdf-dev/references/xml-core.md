# RDF 框架（快开框架）XML 规范

## 概述

本文档定义了将图片转换为快开框架XML的规范，用于指导AI完成以下任务：
1. 解析图片页面结构
2. 匹配快开框架中的布局和组件
3. 根据快开框架XML模型上下文资源，生成符合框架要求的XML

## XML生成位置说明

1. 用户需要指定快开框架前端项目的根目录，指定页面编码（pageCode）和视图编码（viewCode）
2. 找到项目中的 `src/mainEntry` 目录
3. 在 `mainEntry` 目录确定是否存在 `xml` 子目录
   - 如果不存在，创建 `xml` 子目录
   - 如果存在，直接使用 `xml` 子目录
4. 根据页面编码（pageCode）和视图编码（viewCode），在 `xml/pages/{pageCode}/` 目录中创建对应的XML文件：
   - **页面XML文件**：
     - `{pageCode}.page.meta.xml` - 页面元配置
     - `{pageCode}.page.layout.xml` - 页面布局配置
   - **视图XML文件**：
     - `{pageCode}.{viewCode}.view.xml` - 组件视图配置
     - `{pageCode}.{viewCode}.layout.xml` - 视图布局配置

## XML结构规范

快开框架的XML文件主要分为两种类型：**页面XML**和**视图XML**。

### 页面XML结构规范

#### 页面元配置XML (`.page.meta.xml`)
- **文件命名**：`{pageCode}.page.meta.xml`
- **文件路径**：`xml/pages/{pageCode}/{pageCode}.page.meta.xml`
- **用途**：定义页面的元数据配置，包含视图引用、UI状态等
- **核心内容**：
  - `<Page>`：页面根节点，包含`id`、`controller`等属性
  - `<ViewRefs>`：视图引用集合，定义页面中包含的视图
  - `<ViewRef>`：单个视图引用，包含`id`、`refId`、`canFreeDesign`等属性
  - `<UIStates>`：UI状态集合，定义不同状态下的组件状态（如编辑态、浏览态）
- **示例**：
```xml
<Page xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      id="{pageCode}"
      controller="designerctrl/{pageCode}/{PageCode}MainCtrl"
      isChanged="false">
    <ViewRefs>
        <ViewRef id="main" refId="main" canFreeDesign="true"/>
    </ViewRefs>
    <UIStates>
        <UIState id="editState" name="编辑态"/>
        <UIState id="viewState" name="浏览态"/>
    </UIStates>
</Page>
```

#### 页面布局XML (`.page.layout.xml`)
- **文件命名**：`{pageCode}.page.layout.xml`
- **文件路径**：`xml/pages/{pageCode}/{pageCode}.page.layout.xml`
- **用途**：定义页面的整体布局结构，引用视图
- **核心内容**：
  - `<Page>`：页面根节点，包含`id`、`layoutBgColor`、`panelBgColor`、`compDefaultColor`等属性
  - `<ViewRef>`：视图引用，通过`id`属性引用视图
- **示例**：
```xml
<Page xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      id="{pageCode}"
      layoutBgColor="#eef2fd"
      panelBgColor="#fff"
      compDefaultColor="#000">
    <ViewRef id="main" visible="true" showScrollBar="false"/>
</Page>
```

### 视图XML结构规范

#### 组件视图XML (.view.xml)
- **文件命名**：`xxx.xxx.view.xml`
- **用途**：存放组件、模型等详细信息，**不包含布局信息**
- **核心内容**：
  - 组件定义及其属性
  - 数据模型配置
  - 引用节点定义
  - 控制器绑定

#### 布局视图XML (.layout.xml)
- **文件命名**：`xxx.xxx.layout.xml`
- **用途**：描述布局和组件的位置关系
- **核心内容**：
  - 布局结构定义
  - 组件位置关系
  - 布局容器配置
  - 组件尺寸和定位
- **规则**：
  - 通常布局分为layout和panel，panel中只能放layout或单个组件
  - 绝对布局（AbsoluteLayout）、流式布局（FlowLayout）比较特殊，不能放layout，可以放多个组件
  - 表单元素支持放到布局中

### 组件视图XML (.view.xml) 结构

**示例**：
```xml
<View
    id="loginPage"
    isDialog="false"
    isCustom="true"
    controller="loginController"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">

    <!-- 数据模型 -->
    <DataModels>
        <Dataset id="loginDataset" isLazyLoad="false" isEdit="true">
            <Fields>
                <Field id="username" text="用户名" isRequire="true" dataType="String"/>
                <Field id="password" text="密码" isRequire="true" dataType="String"/>
            </Fields>
        </Dataset>
    </DataModels>

    <!-- 组件定义 -->
    <Controls>
        <Label id="titleText" text="登录页面" fontSize="24"/>
        <Input id="usernameInput" placeholder="请输入用户名"/>
        <Input id="passwordInput" placeholder="请输入密码" inputType="password"/>
        <Button id="loginButton" text="登录" backgroundColor="#007AFF"/>
    </Controls>
</View>
```

### 布局视图XML (.layout.xml) 结构

**示例**：
```xml
<View
    id="loginPage"
    isFlow="false"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">

    <!-- 垂直流布局 -->
    <FlowVLayout id="mainLayout" height="100%" cssStyle="padding:20px;">
        <FlowVPanel id="titlePanel">
            <Label id="titleText" width="100%" height="40"/>
        </FlowVPanel>
        <FlowVPanel id="usernamePanel">
            <Input id="usernameInput" width="100%" height="45"/>
        </FlowVPanel>
        <FlowVPanel id="passwordPanel">
            <Input id="passwordInput" width="100%" height="45"/>
        </FlowVPanel>
        <FlowVPanel id="loginButtonPanel">
            <Button id="loginButton" width="100%" height="45"/>
        </FlowVPanel>
    </FlowVLayout>
</View>
```

## 转换规则

### 元素识别
- 自动识别常见UI元素：按钮、输入框、文本、图片、列表、容器等
- 基于视觉特征（形状、颜色、纹理）和位置关系进行分类
- 优先识别结构清晰、边界明确的元素
- 如果在一个区域有多个输入框类型组件可以尝试合并为表单组件

### 坐标映射
- 采用相对坐标系统，基于页面宽度和高度
- 坐标值范围：0-1
- 保留整数即可

### 属性提取
- 从图片中提取元素的视觉属性：颜色、字体、大小、边框等
- 智能推断元素的功能属性：如按钮的文本内容、输入框的占位符等
- 生成符合快开框架要求的标准化属性值
- 对于无法直接提取的属性，使用合理默认值

## 命名规范

### ID命名规则
- **命名方式**：采用功能英文驼峰命名法，如 `loginButton`、`userNameInput`
- **唯一性要求**：同一文件内的ID必须唯一
- **一致性要求**：同一个页面的 `.view.xml` 和 `.layout.xml` 中对应的组件ID必须保持一致
- **语义化要求**：ID应清晰反映组件的功能和用途

## XML生成流程

### 页面XML生成流程
1. 生成 `.page.meta.xml`：创建 `<Page>` 根节点，定义视图引用
2. 生成 `.page.layout.xml`：创建页面布局引用

### 视图XML生成流程
1. **阶段一**：生成 `.layout.xml`，描述布局结构和组件位置
2. **阶段二**：生成 `.view.xml`，包含组件和数据模型的详细属性

### 元素到组件的映射规则

| 图片元素 | RDF组件 | 必需绑定 |
|---------|---------|---------|
| 表格 | Grid | Dataset |
| 表单 | Form | Dataset |
| 动态表单 | DynamicForm | Dataset |
| 下拉框 | Select | DataList |
| 单选按钮组 | RadioGroup | DataList |
| 复选框组 | CheckboxGroup | DataList |
| 复选框 | Checkbox | DataList（可选） |
