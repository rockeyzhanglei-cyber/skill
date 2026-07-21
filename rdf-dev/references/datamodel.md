# 数据模型核心参考

## 概述

数据模型用于定义页面所需的数据结构，包括数据集（Dataset）、数据列表（DataList）等。

## 核心模型快速参考

| 模型 | XML标签 | 用途 | 必需子元素 | 绑定组件 |
|------|---------|------|------------|----------|
| Dataset | Dataset | 数据集 | Fields | Form, Grid, DynamicForm |
| DataList | DataList | 数据列表 | DataItem | Select, RadioGroup, CheckboxGroup |

## Dataset（数据集）

### 核心属性（必填）

- **id**: 唯一标识（必填）
- **isLazyLoad**: 是否懒加载（默认false）
- **isEdit**: 是否可编辑（默认false）

### 典型示例

```xml
<Dataset id="patientDataset" isLazyLoad="false" pageSize="20" isEdit="true">
    <Fields>
        <Field id="id" text="ID" dataType="string" field="id" isPK="true"/>
        <Field id="name" text="姓名" dataType="string" field="name" isRequire="true"/>
        <Field id="age" text="年龄" dataType="number" field="age"/>
    </Fields>
</Dataset>
```

## Field（字段）

### 核心属性

| 属性名 | 描述 | 类型 | 必填 |
|--------|------|------|------|
| id | 字段唯一标识 | string | 是 |
| text | 字段显示名称 | string | 否 |
| dataType | 数据类型 | string | 否 |
| field | 字段名 | string | 否 |
| isPK | 是否主键 | boolean | 否 |
| isRequire | 是否必填 | boolean | 否 |

## DataList（数据列表）

### 核心属性

- **id**: 唯一标识（必填）

### 典型示例

```xml
<DataList id="statusList" caption="状态列表">
    <DataItem text="启用" value="1" visible="true"/>
    <DataItem text="禁用" value="0" visible="true"/>
</DataList>
```

## DataItem（数据项）

### 核心属性

| 属性名 | 描述 | 类型 | 必填 |
|--------|------|------|------|
| text | 显示文本 | string | 否 |
| value | 值 | string | 否 |
| visible | 是否可见 | boolean | 否 |

## 组件绑定数据模型规则

| 组件 | 必需绑定 | 说明 |
|------|----------|------|
| Grid | Dataset | 表格必须绑定数据集 |
| Form | Dataset | 表单必须绑定数据集 |
| DynamicForm | Dataset | 动态表单必须绑定数据集 |
| Select | DataList | 下拉框必须绑定数据列表 |
| RadioGroup | DataList | 单选按钮组必须绑定数据列表 |
| CheckboxGroup | DataList | 复选框组必须绑定数据列表 |
| Checkbox | DataList（可选） | 复选框可选绑定数据列表 |

## 常用数据类型

- **string**: 字符串
- **number**: 数字
- **boolean**: 布尔值
- **date**: 日期
- **datetime**: 日期时间
