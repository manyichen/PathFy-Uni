import { LineChart, RadarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([RadarChart, LineChart, CanvasRenderer, GridComponent, LegendComponent, TooltipComponent])

export { VChart }
