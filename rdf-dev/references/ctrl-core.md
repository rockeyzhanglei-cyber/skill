# RDF 框架（快开框架）控制类核心说明

## 概述

控制类是 RDF 框架中用来实现业务逻辑的类。它负责调用后端接口、设置前端页面的状态、处理用户交互等。

## 控制类文件生成规则

### 一般控制类

负责处理页面的业务逻辑，调用后端接口、设置前端页面的状态、处理用户交互等。

#### 生成规则（强制）

- **生成位置**：`src/mainEntry/ctrl/{PageCode}/{PageCode}{ViewCode}Ctrl.ts`
- **文件命名规则**：page编码 + view编码 + Ctrl.ts，驼峰命名法，首字母大写
- **类名**：`{PageCode}{ViewCode}Ctrl`
- **初始内容**：
```typescript
import {MouseEvent} from "pango-framework-vue";
export default class {PageCode}{ViewCode}Ctrl {

}
```

#### 注册规则（强制）

控制类需要在控制类相对路径 `../index.ts` 中注册：
```typescript
import {PageCode}{ViewCode}Ctrl from "./{PageCode}/{PageCode}{ViewCode}Ctrl";
export default {
    {PageCode}{ViewCode}Ctrl,
};
```

### 渲染控制类

负责处理页面的渲染逻辑，根据模型数据渲染前端页面。

#### 生成规则（强制）

- **生成位置**：`src/mainEntry/ctrl/{PageCode}/{PageCode}Render.tsx`
- **文件命名规则**：page编码 + Render.tsx，驼峰命名法，首字母大写
- **类名**：`{PageCode}Render`
- **初始内容**：
```typescript
import {Button} from "pango-framework-vue";
export default class {PageCode}Render {

}
```

#### 注册规则（强制）

渲染控制类需要在渲染控制类相对路径 `../index.ts` 中注册：
```typescript
import {PageCode}Render from "./{PageCode}/{PageCode}Render";
export default {
    {PageCode}Render,
};
```

## 事件方法生成规则（强制）

### 一般控制类事件方法

1. **事件方法来源**：view.xml、layout.xml中定义的`<Event>`标签的`method`属性
2. **事件方法命名规则**：组件ID + `<Event>`标签的eventName属性（驼峰命名法，首字母大写）
   - 示例：组件ID为`queryButton`，事件为`onClick`，方法名为`queryButtonOnClick`
3. **事件方法参数**：
   - 事件参数模型（如`MouseEvent<YButton>`、`TextEvent<YInput>`等）
   - 部分事件参数存在泛型：`MouseEvent`、`TextEvent`、`KeyEvent`、`FocusEvent`等
   - 泛型是配置事件的组件/布局的模型（`YButton`、`YView`等）
4. **事件方法返回值**：`void`

### 渲染控制类渲染方法

**渲染方法来源**：
- **表格操作列自定义渲染**（view.xml中的GridColumn标签）：
  - `renderType`等于`CustomRender`时，才会生成自定义渲染方法
  - `customRender`指定自定义渲染方法名
  - `controller`指定自定义渲染类
- **布局Panel自定义渲染**（layout.xml中的FlowHPanel标签、FlowVPanel标签）：
  - `controller`指定自定义渲染类
  - `render`指定自定义渲染方法，必须返回一个节点

**渲染方法命名规则**：以`Render`结尾，驼峰命名，首字母小写。不可重复。

**渲染方法参数**：
- **表格操作列自定义渲染**：
  - `text`: 表格列文本
  - `record`: 表格行数据
  - `index`: 表格行索引
  - `field`: 表格列字段
  - `column`: 表格列实例
  - `row`: 表格行实例
- **布局Panel自定义渲染**：
  - `yPanel`: 布局Panel组件模型
  - `yView`: Panel所在View组件模型

**渲染方法返回值**：标签节点（不需要明确返回值类型）

## 示例

### 一般控制类示例

```typescript
import {MouseEvent, TextEvent} from "pango-framework-vue";
import {YButton, YInput} from "pango-framework-vue";

export default class LoginMainCtrl {

    // 按钮点击事件
    public loginButtonOnClick(e: MouseEvent<YButton>): void {
        // 处理登录逻辑
    }

    // 输入框值变化事件
    public usernameInputOnValueChange(e: TextEvent<YInput>): void {
        // 处理值变化
    }
}
```

### 渲染控制类示例

```typescript
import {Button} from "pango-framework-vue";
import {WButton} from 'win-design-next';

export default class LoginRender {

    // 表格操作列渲染
    operationRender(text, record, index, field, column, row) {
        return (
            <div style={{ display: 'flex', gap: '8px' }}>
                <WButton type="primary" size="small" onClick={() => this.handleEdit(row)}>
                    编辑
                </WButton>
                <WButton type="danger" size="small" onClick={() => this.handleDelete(row)}>
                    删除
                </WButton>
            </div>
        );
    }

    // 布局Panel渲染
    customPanelRender(yPanel, yView) {
        return (
            <div style={{ padding: '20px' }}>
                <span>自定义内容</span>
            </div>
        );
    }
}
```
