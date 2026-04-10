# Chip Model Analysis

## Current Status

- No half-written `outputs/chip_model_analysis` artifacts were present before this run.
- The machine still has many old `node/cmd/powershell/python` processes, but there is no sign that the previous chip extraction task was still actively writing output.

## chip save keys

- `CHIP_EDITOR_SAVE_POSITION_KEY` = `chip_editor_position`
- `CHIP_EDITOR_SAVE_ZOOM_KEY` = `chip_editor_zoom`
- `CHIP_ID_KEY` = `chip_id`
- `CHIP_SAVE_GRAPH_KEY` = `chip_graph`
- `CHIP_SAVE_INPUTS_KEY` = `chip_inputs`
- `CHIP_SAVE_OUTPUTS_KEY` = `chip_outputs`
- `CHIP_SAVE_PERIOD_NAME_INDEX_KEY` = `chip_period_name_index`
- `CHIP_SAVE_PRIORITY_KEY` = `chip_priority`
- `CHIP_SAVE_TPS_KEY` = `chip_tps`
- `CHIP_SAVE_VARIABLES_KEY` = `chip_variables`
- `CHIP_SAVE_VISUAL_NAME_KEY` = `chip_visual_name`

## GateDataType

- `None` = `0`
- `Entity` = `1`
- `Number` = `2`
- `String` = `4`
- `Vector` = `8`
- `Color` = `24`
- `IntegerNumber` = `32`
- `Dynamic` = `64`
- `ArrayNumber` = `128`
- `ArrayString` = `256`
- `ArrayVector` = `512`
- `ArrayEntity` = `1024`
- `Array` = `2048`
- `Any` = `4095`

## NodeOperationType summary

- Total operation types: `169`
- Total node view models: `153`

## Module counts

- `Arrays`: `8`
- `Base`: `88`
- `Comparisons`: `8`
- `Memory`: `10`
- `Trigonometry`: `34`
- `WorldSession`: `5`

## Sample nodes

- `AbsNodeViewModel` | module=`Base` | op=`Abs` | in=`Dynamic` | out=`Dynamic`
- `AccumulateNodeViewModel` | module=`Memory` | op=`Accumulate` | in=`Number | Number` | out=`Number`
- `AcosNodeViewModel` | module=`Trigonometry` | op=`Acos` | in=`Number` | out=`Number`
- `ActivateEntityNodeViewModel` | module=`Base` | op=`Activate` | in=`Entity | Number` | out=`Number`
- `AddAngularForceEntityNodeViewModel` | module=`Base` | op=`AddAngularForce` | in=`Entity | Number` | out=`none`
- `AddForceEntityNodeViewModel` | module=`Base` | op=`AddForce` | in=`Entity | Vector` | out=`none`
- `AddNumbersNodeViewModel` | module=`Base` | op=`Add` | in=`Dynamic | Dynamic` | out=`Dynamic`
- `AddOffsetForceEntityNodeViewModel` | module=`Base` | op=`AddForceAtPosition` | in=`Entity | Vector | Vector` | out=`none`
- `AndNodeViewModel` | module=`Base` | op=`And` | in=`Number | Number` | out=`Number`
- `AngleEntityNodeViewModel` | module=`Base` | op=`EntityAngle` | in=`Entity | Number` | out=`Number`
- `AngularVelocityEntityNodeViewModel` | module=`Base` | op=`AngularVelocity` | in=`Entity | Number` | out=`Number`
- `ArcCTanNodeViewModel` | module=`Trigonometry` | op=`Actan` | in=`Number` | out=`Number`
- `ArraysAddNodeViewModel` | module=`Arrays` | op=`ArraysAdd` | in=`Dynamic | Dynamic | IntegerNumber | IntegerNumber` | out=`Dynamic | IntegerNumber`
- `ArraysClearNodeViewModel` | module=`Arrays` | op=`ArraysClear` | in=`Dynamic | IntegerNumber` | out=`Dynamic`
- `ArraysFindNodeViewModel` | module=`Arrays` | op=`ArraysFind` | in=`Dynamic | Dynamic | IntegerNumber | IntegerNumber` | out=`IntegerNumber`
- `ArraysGetNodeViewModel` | module=`Arrays` | op=`ArraysGet` | in=`Dynamic | IntegerNumber` | out=`Dynamic | IntegerNumber`
- `ArraysLengthNodeViewModel` | module=`Arrays` | op=`ArraysLength` | in=`Dynamic` | out=`IntegerNumber`
- `ArraysRemoveAllByValueNodeViewModel` | module=`Arrays` | op=`ArraysRemoveAllByValue` | in=`Dynamic | Dynamic | IntegerNumber` | out=`Dynamic`
- `ArraysRemoveByIndexNodeViewModel` | module=`Arrays` | op=`ArraysRemoveByIndex` | in=`Dynamic | IntegerNumber | IntegerNumber` | out=`Dynamic`
- `ArraysSetNodeViewModel` | module=`Arrays` | op=`ArraysSet` | in=`Dynamic | IntegerNumber | Dynamic | IntegerNumber` | out=`Dynamic`
