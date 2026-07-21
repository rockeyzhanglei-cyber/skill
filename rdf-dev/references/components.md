# RDF 组件快速参考

## 展示类组件

| 组件 | XML标签 | 必需绑定 | 用途 |
|-----|---------|---------|------|
| Label | Label | 无 | 文本显示 |
| LabelGroup | LabelGroup | DataList(可选) | 标签组 |
| Grid | Grid | Dataset | 表格数据展示 |
| Form | Form | Dataset | 表单数据录入 |
| DynamicForm | DynamicForm | Dataset | 动态表单 |
| List | List | Dataset | 列表展示 |
| Tree | Tree | Dataset | 树形结构 |
| Progress | Progress | 无 | 进度条 |

### Grid（表格）示例

```xml
<DataModels>
    <Dataset id="userDataset" isLazyLoad="false" isEdit="true">
        <Fields>
            <Field id="id" text="ID" dataType="String" field="id"/>
            <Field id="name" text="姓名" dataType="String" field="name"/>
        </Fields>
    </Dataset>
</DataModels>
<Grid id="userGrid" dataset="userDataset" isEdit="true">
    <GridColumn id="id" field="id" text="ID" width="100"/>
    <GridColumn id="name" field="name" text="姓名" width="150"/>
</Grid>
```

### Form（表单）示例

```xml
<DataModels>
    <Dataset id="formDataset" isLazyLoad="false" isEdit="true">
        <Fields>
            <Field id="name" text="姓名" dataType="String" field="name"/>
            <Field id="age" text="年龄" dataType="Number" field="age"/>
        </Fields>
    </Dataset>
</DataModels>
<Form id="userForm" dataset="formDataset" column="2" labelWidth="100">
    <Element id="name" field="name" labelText="姓名">
        <Input id="nameInput"/>
    </Element>
    <Element id="age" field="age" labelText="年龄">
        <NumberInput id="ageInput"/>
    </Element>
</Form>
```

## 输入类组件

| 组件 | XML标签 | 必需绑定 | 用途 |
|-----|---------|---------|------|
| Input | Input | 无 | 文本输入 |
| TextArea | TextArea | 无 | 多行文本 |
| NumberInput | NumberInput | 无 | 数字输入 |
| PasswordInput | PasswordInput | 无 | 密码输入 |
| DateInput | DateInput | 无 | 日期选择 |
| TimePick | TimePick | 无 | 时间选择 |
| ColorPicker | ColorPicker | 无 | 颜色选择 |

## 选择类组件

| 组件 | XML标签 | 必需绑定 | 用途 |
|-----|---------|---------|------|
| Select | Select | DataList | 下拉框 |
| RadioGroup | RadioGroup | DataList | 单选按钮组 |
| Checkbox | Checkbox | DataList(可选) | 复选框 |
| CheckboxGroup | CheckboxGroup | DataList | 复选框组 |
| Switch | Switch | 无 | 开关 |
| ReferenceInput | ReferenceInput | 无 | 引用选择 |

### Select（下拉框）示例

```xml
<DataModels>
    <DataList id="statusList">
        <DataItem text="启用" value="1"/>
        <DataItem text="禁用" value="0"/>
    </DataList>
</DataModels>
<Select id="statusSelect" datalist="statusList"/>
```

## 操作类组件

| 组件 | XML标签 | 必需绑定 | 用途 |
|-----|---------|---------|------|
| Button | Button | 无 | 按钮 |
| Link | Link | 无 | 链接 |
| FileUpload | FileUpload | 无 | 文件上传 |
| Toolbar | Toolbar | 无 | 工具栏 |

### Button（按钮）示例

```xml
<Button id="submitButton" text="提交" status="primary" classType="normal"/>
```

## 组件通用属性

| 属性名 | 描述 | 类型 | 默认值 |
|--------|------|------|--------|
| id | 唯一标识 | string | - |
| visible | 是否可见 | boolean | true |
| disabled | 禁用 | boolean | false |
| required | 必填 | boolean | false |
| value | 值 | string | - |

## 布局属性（在 layout.xml 中设置）

所有组件在 layout.xml 中支持以下属性：
- `width`: 宽度
- `height`: 高度
- `top`: 上边距
- `left`: 左边距
- `position`: 定位方式（absolute/relative）

**重要**：layout.xml 中的 `width` 优先使用数值，避免使用百分比。
