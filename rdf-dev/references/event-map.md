# RDF 组件事件映射表

## 事件类型说明

| 事件类型 | 说明 | 是否有泛型 |
|---------|------|-----------|
| MouseEvent | 鼠标事件 | 是 |
| TextEvent | 文本/值变化事件 | 是 |
| KeyEvent | 键盘事件 | 是 |
| FocusEvent | 焦点事件 | 是 |
| GridEvent | 表格事件 | 否 |
| GridRowEvent | 表格行事件 | 否 |
| DialogEvent | 对话框事件 | 否 |
| ViewEvent | 视图事件 | 否 |
| DatasetEvent | 数据集事件 | 否 |

**注意**：MouseEvent、TextEvent、KeyEvent、FocusEvent 需要泛型参数，泛型是配置事件的组件模型（如`YButton`、`YInput`等）。

## 常用组件事件映射

| 组件 | 事件类型 | 事件名称 |
|------|---------|----------|
| YButton | MouseEvent | onClick, onMouseover, onMouseout |
| YInput | TextEvent | onValueChange, onChange, onClear |
| YInput | KeyEvent | onEnter, onKeyUp, onKeyDown |
| YInput | FocusEvent | onFocus, onBlur |
| YSelect | TextEvent | onValueChange, onSelect, onClear |
| YGrid | GridRowEvent | onRowClick, onRowSelected, onRowDbClick |
| YGrid | GridCellEvent | onCellClick, cellValueChanged, beforeEdit |
| YCheckbox | TextEvent | onValueChange |
| YRadioGroup | TextEvent | onValueChange |
| YForm | FocusEvent | onFocus, onBlur |
| YView | ViewEvent | beforeRender, afterRender, onClosed |
| Dataset | DatasetEvent | onDataLoad, onAfterRowSelect |

## 事件绑定示例

### XML 中绑定事件
```xml
<Button id="submitButton">
    <Events>
        <Event eventName="onClick" method="submitButtonOnClick" controller="page/view/ViewCtrl" eventType="MouseEvent"/>
    </Events>
</Button>
```

### 控制类中实现方法

```typescript
// 方法命名：组件ID + 事件名称（首字母大写）
public submitButtonOnClick(e: MouseEvent<YButton>): void {
    // 处理逻辑
}
```

## 常用组件事件参数类型

| 组件 | 事件 | 参数类型 |
|------|------|---------|
| Button | onClick | MouseEvent<YButton> |
| Input | onValueChange | TextEvent<YInput> |
| Input | onEnter | KeyEvent<YInput> |
| Select | onValueChange | TextEvent<YSelect> |
| Grid | onRowClick | GridRowEvent |
| Checkbox | onValueChange | TextEvent<YCheckbox> |

## 快速查找

### 按事件类型查找组件

**MouseEvent（需要泛型）**：YButton, YForm, YGrid, YImage, YLabel, YSelect, YInput, YNumberInput

**TextEvent（需要泛型）**：YInput, YSelect, YCheckbox, YRadioGroup, YTextArea, YNumberInput, YDateInput

**KeyEvent（需要泛型）**：YInput, YSelect, YTextArea, YNumberInput

**FocusEvent（需要泛型）**：YInput, YSelect, YTextArea, YNumberInput, YDateInput

**GridRowEvent**：YGrid

**DatasetEvent**：Dataset
