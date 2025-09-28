# Marketing Dashboard Documentation

## Overview

The Marketing Dashboard provides a comprehensive view of marketing campaign performance, channel distribution, conversion metrics, and other key marketing KPIs for the BMAsia CRM system.

## Features

### 1. Campaign Performance KPIs
- **Active Campaigns Count**: Number of currently running campaigns
- **Total Reach/Impressions**: Total audience reached across all campaigns
- **Conversion Rate**: Percentage of visitors who convert to customers
- **ROI (Return on Investment)**: Marketing spend effectiveness
- **Email Open Rate**: Email campaign engagement metrics
- **Click-Through Rate**: Campaign link engagement

### 2. Visual Components

#### Campaign Performance Chart (`CampaignPerformanceChart.tsx`)
- Multi-metric visualization (impressions, clicks, conversions, spend)
- Multiple chart types: Line, Area, and Composed charts
- Time-based performance tracking
- Interactive tooltips and trend analysis

#### Channel Distribution Chart (`ChannelDistributionChart.tsx`)
- Pie and bar chart visualizations
- Performance breakdown by channel (Email, Social, Web, Mobile, Search)
- Channel performance comparison
- Cost effectiveness analysis

#### Conversion Funnel Chart (`ConversionFunnelChart.tsx`)
- Visual funnel representation with drop-off analysis
- Optimization recommendations
- Stage-by-stage conversion tracking
- Performance insights and bottleneck identification

#### Campaign Calendar View (`CampaignCalendarView.tsx`)
- Monthly calendar view of campaign schedules
- Campaign start/end date tracking
- Status indicators for different campaign states
- Upcoming milestones and deadlines

### 3. Marketing-Specific Features

#### Campaign Status Cards
- Active, Scheduled, Completed, and Paused campaign overview
- Budget vs spend tracking
- ROAS (Return on Ad Spend) metrics
- Channel-specific performance indicators

#### A/B Testing Results
- Campaign variant performance comparison
- Statistical confidence levels
- Winner identification and conversion rate analysis

#### Top Performing Content
- Content performance metrics (views, leads, engagement)
- Content type breakdown (blog, video, ebook, webinar, infographic)
- Lead generation effectiveness

#### Social Media Engagement
- Platform-specific follower and engagement metrics
- Reach and posting frequency analysis
- Multi-platform performance comparison

#### Budget vs Spend Tracking
- Real-time budget utilization
- Campaign efficiency metrics
- Spend optimization insights

#### Lead Generation Metrics
- Monthly lead generation trends
- Qualified vs total leads analysis
- Lead quality tracking

### 4. Data Export Capabilities
- **PDF Export**: Complete dashboard export for reporting
- **Excel Export**: Detailed data export with multiple sheets
  - KPIs summary
  - Campaign performance data
  - Channel performance metrics
  - A/B test results
  - Content performance data

## Color Scheme

The Marketing Dashboard uses an orange/deep orange color scheme to distinguish it from other departmental dashboards:

- **Primary**: `#ff6f00` (Deep Orange)
- **Secondary**: `#ff8f00` (Orange)
- **Accent**: `#ffb74d` (Light Orange)
- **Success**: `#4caf50` (Green)
- **Warning**: `#ff9800` (Amber)
- **Error**: `#f44336` (Red)
- **Info**: `#2196f3` (Blue)

## Responsive Design

The dashboard is fully responsive and optimized for:
- **Desktop**: Full feature set with multi-column layouts
- **Tablet**: Adaptive grid system with stacked components
- **Mobile**: Single-column layout with touch-friendly interfaces

## Usage

### Import and Use

```typescript
import MarketingDashboard from './components/MarketingDashboard';

// In your app or routing component
<MarketingDashboard />
```

### Time Filters

The dashboard supports multiple time filter options:
- Today
- This Week
- This Month
- This Quarter
- This Year

### Data Refresh

- **Auto-refresh**: Every 5 minutes
- **Manual refresh**: Click the refresh button
- **Last updated**: Timestamp displayed in header

## Mock Data

The dashboard currently uses comprehensive mock data that demonstrates:
- Multiple campaign types and statuses
- Realistic performance metrics
- Historical trend data
- A/B testing scenarios
- Content performance variations
- Social media engagement patterns

## Dependencies

The Marketing Dashboard relies on the following key dependencies:
- **@mui/material**: UI components and theming
- **@mui/icons-material**: Icon components
- **recharts**: Chart visualization library
- **date-fns**: Date manipulation and formatting
- **html2canvas & jsPDF**: PDF export functionality
- **xlsx**: Excel export functionality

## File Structure

```
src/components/
├── MarketingDashboard.tsx          # Main dashboard component
└── charts/
    ├── CampaignPerformanceChart.tsx # Campaign metrics over time
    ├── ChannelDistributionChart.tsx # Channel performance breakdown
    ├── ConversionFunnelChart.tsx    # Conversion funnel visualization
    └── CampaignCalendarView.tsx     # Campaign scheduling calendar
```

## Customization

### Adding New Metrics
1. Update the `MarketingKPIs` interface
2. Add new KPI cards in the dashboard grid
3. Update mock data generators
4. Include in export functionality

### Adding New Chart Types
1. Create new chart component in `/charts` folder
2. Follow existing component patterns
3. Import and integrate into main dashboard
4. Update responsive grid layout

### Styling Customization
- Modify `MARKETING_COLORS` constant for color scheme changes
- Update card layouts and spacing in component styling
- Customize chart colors and themes in individual components

## Performance Considerations

- Components use React.memo() where appropriate
- Charts are optimized with ResponsiveContainer
- Large datasets are paginated or truncated
- Export functions include loading states
- Auto-refresh can be disabled if needed

## Future Enhancements

Potential areas for expansion:
- Real-time campaign monitoring
- Advanced A/B testing analytics
- Predictive performance modeling
- Integration with external marketing platforms
- Custom dashboard layouts
- Advanced filtering and segmentation
- Marketing automation workflow visualization