import React from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { Box, Container, CircularProgress, Typography, Paper } from '@mui/material';
import { useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Companies from './pages/Companies';
import CompanyDetail from './pages/CompanyDetail';
import CompanyNew from './pages/CompanyNew';
import CompanyEdit from './pages/CompanyEdit';
import Opportunities from './pages/Opportunities';
import OpportunityDetail from './pages/OpportunityDetail';
import Tasks from './pages/Tasks';
import Contracts from './pages/Contracts';
import ContractDetail from './pages/ContractDetail';
import Invoices from './pages/Invoices';
import Contacts from './pages/Contacts';
import Quotes from './pages/Quotes';
import QuoteDetail from './pages/QuoteDetail';
import SalesTargets from './pages/SalesTargets';
import Campaigns from './pages/Campaigns';
import CampaignCreate from './pages/CampaignCreate';
import CampaignDetail from './pages/CampaignDetail';
import EmailTemplates from './pages/EmailTemplates';
import EmailAutomations from './pages/EmailAutomations';
import SequenceDetail from './pages/SequenceDetail';
import Segments from './pages/Segments';
import SegmentForm from './pages/SegmentForm';
import Tickets from './pages/Tickets';
import TicketDetail from './pages/TicketDetail';
import TicketForm from './pages/TicketForm';
import KnowledgeBase from './pages/KnowledgeBase';
import KnowledgeBaseArticle from './pages/KnowledgeBaseArticle';
import KBArticleNew from './pages/KBArticleNew';
import KBArticleEdit from './pages/KBArticleEdit';
import KBSettings from './pages/KBSettings';
import ZonesUnified from './pages/ZonesUnified';
import ZoneDetail from './pages/ZoneDetail';
import ZoneNew from './pages/ZoneNew';
import ZoneEdit from './pages/ZoneEdit';
import Users from './pages/Users';
import MyProfile from './pages/MyProfile';
import Settings from './pages/Settings';
import RevenueDashboard from './pages/RevenueDashboard';
import AccountsReceivable from './pages/AccountsReceivable';
import AccountsPayable from './pages/AccountsPayable';
import ProfitLoss from './pages/ProfitLoss';
import CashFlow from './pages/CashFlow';
import BalanceSheet from './pages/BalanceSheet';
import ContractTemplates from './pages/ContractTemplates';
// import LoadingSkeleton from './components/LoadingSkeleton';

// Temporary placeholder components for new routes
const PlaceholderPage: React.FC<{ title: string }> = ({ title }) => (
  <Paper sx={{ p: 3 }}>
    <Typography variant="h4" gutterBottom>
      {title}
    </Typography>
    <Typography variant="body1" color="text.secondary">
      This page is coming soon! The navigation structure is ready and this will be implemented next.
    </Typography>
  </Paper>
);

// Protected Layout wrapper component
const ProtectedLayout: React.FC = () => {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <Layout>
      <Container maxWidth="xl" sx={{ mt: 2, mb: 2 }}>
        <Outlet />
      </Container>
    </Layout>
  );
};

function App() {
  const { isAuthenticated, loading } = useAuth();

  return (
    <Routes>
      {/* Login Route - Public */}
      <Route path="/login" element={<Login />} />

      {/* Root Route - Redirect based on auth status */}
      <Route
        path="/"
        element={
          loading ? (
            <Box
              display="flex"
              flexDirection="column"
              justifyContent="center"
              alignItems="center"
              minHeight="100vh"
              gap={2}
            >
              <CircularProgress size={40} />
              <Typography variant="body1">Initializing BMAsia CRM...</Typography>
            </Box>
          ) : isAuthenticated ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      {/* Protected Routes - All wrapped in ProtectedLayout */}
      <Route element={<ProtectedLayout />}>
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute requiredModule="dashboard">
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/companies"
          element={
            <ProtectedRoute requiredModule="companies">
              <Companies />
            </ProtectedRoute>
          }
        />
        <Route
          path="/companies/new"
          element={
            <ProtectedRoute requiredModule="companies">
              <CompanyNew />
            </ProtectedRoute>
          }
        />
        <Route
          path="/companies/:id"
          element={
            <ProtectedRoute requiredModule="companies">
              <CompanyDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/companies/:id/edit"
          element={
            <ProtectedRoute requiredModule="companies">
              <CompanyEdit />
            </ProtectedRoute>
          }
        />
        <Route
          path="/opportunities"
          element={
            <ProtectedRoute requiredModule="opportunities">
              <Opportunities />
            </ProtectedRoute>
          }
        />
        <Route
          path="/opportunities/:id"
          element={
            <ProtectedRoute requiredModule="opportunities">
              <OpportunityDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tasks"
          element={
            <ProtectedRoute requiredModule="tasks">
              <Tasks />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tasks/:id"
          element={
            <ProtectedRoute requiredModule="tasks">
              <Tasks />
            </ProtectedRoute>
          }
        />
        <Route
          path="/contracts"
          element={
            <ProtectedRoute requiredModule="contracts">
              <Contracts />
            </ProtectedRoute>
          }
        />
        <Route
          path="/contracts/:id"
          element={
            <ProtectedRoute requiredModule="contracts">
              <ContractDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/invoices"
          element={
            <ProtectedRoute requiredModule="invoices">
              <Invoices />
            </ProtectedRoute>
          }
        />
        <Route
          path="/revenue"
          element={
            <ProtectedRoute requiredModule="invoices">
              <RevenueDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/finance/ar"
          element={
            <ProtectedRoute requiredModule="invoices">
              <AccountsReceivable />
            </ProtectedRoute>
          }
        />
        <Route
          path="/finance/ap"
          element={
            <ProtectedRoute requiredModule="invoices">
              <AccountsPayable />
            </ProtectedRoute>
          }
        />
        <Route
          path="/finance/pl"
          element={
            <ProtectedRoute requiredModule="invoices">
              <ProfitLoss />
            </ProtectedRoute>
          }
        />
        <Route
          path="/finance/cash-flow"
          element={
            <ProtectedRoute requiredModule="invoices">
              <CashFlow />
            </ProtectedRoute>
          }
        />
        <Route
          path="/finance/balance-sheet"
          element={
            <ProtectedRoute requiredModule="invoices">
              <BalanceSheet />
            </ProtectedRoute>
          }
        />

        {/* New navigation routes */}
        <Route path="/quick-actions" element={<PlaceholderPage title="Quick Actions" />} />
        <Route
          path="/contacts"
          element={
            <ProtectedRoute requiredModule="contacts">
              <Contacts />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quotes"
          element={
            <ProtectedRoute requiredModule="quotes">
              <Quotes />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quotes/:id"
          element={
            <ProtectedRoute requiredModule="quotes">
              <QuoteDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/targets"
          element={
            <ProtectedRoute requiredModule="targets">
              <SalesTargets />
            </ProtectedRoute>
          }
        />
        <Route path="/my-queue" element={<PlaceholderPage title="My Task Queue" />} />

        {/* Marketing routes */}
        <Route
          path="/campaigns"
          element={
            <ProtectedRoute requiredModule="campaigns">
              <Campaigns />
            </ProtectedRoute>
          }
        />
        <Route
          path="/campaigns/new"
          element={
            <ProtectedRoute requiredModule="campaigns">
              <CampaignCreate />
            </ProtectedRoute>
          }
        />
        <Route
          path="/campaigns/:id"
          element={
            <ProtectedRoute requiredModule="campaigns">
              <CampaignDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/email-templates"
          element={
            <ProtectedRoute requiredModule="campaigns">
              <EmailTemplates />
            </ProtectedRoute>
          }
        />
        <Route
          path="/email-automations"
          element={
            <ProtectedRoute requiredModule="campaigns">
              <EmailAutomations />
            </ProtectedRoute>
          }
        />
        <Route
          path="/email-automations/:id"
          element={
            <ProtectedRoute requiredModule="campaigns">
              <SequenceDetail />
            </ProtectedRoute>
          }
        />
        {/* Backward compatibility redirect */}
        <Route
          path="/email-sequences"
          element={<Navigate to="/email-automations" replace />}
        />
        <Route
          path="/email-sequences/:id"
          element={<Navigate to="/email-automations" replace />}
        />
        <Route path="/analytics" element={<PlaceholderPage title="Marketing Analytics" />} />
        <Route
          path="/segments"
          element={
            <ProtectedRoute requiredModule="campaigns">
              <Segments />
            </ProtectedRoute>
          }
        />
        <Route
          path="/segments/new"
          element={
            <ProtectedRoute requiredModule="campaigns">
              <SegmentForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/segments/:id/edit"
          element={
            <ProtectedRoute requiredModule="campaigns">
              <SegmentForm />
            </ProtectedRoute>
          }
        />

        {/* Tech Support routes */}
        <Route
          path="/tickets"
          element={
            <ProtectedRoute requiredModule="tickets">
              <Tickets />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tickets/new"
          element={
            <ProtectedRoute requiredModule="tickets">
              <TicketForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tickets/:id"
          element={
            <ProtectedRoute requiredModule="tickets">
              <TicketDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tickets/:id/edit"
          element={
            <ProtectedRoute requiredModule="tickets">
              <TicketForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/knowledge-base"
          element={
            <ProtectedRoute requiredModule="tickets">
              <KnowledgeBase />
            </ProtectedRoute>
          }
        />
        <Route
          path="/knowledge-base/new"
          element={
            <ProtectedRoute requiredModule="tickets">
              <KBArticleNew />
            </ProtectedRoute>
          }
        />
        <Route
          path="/knowledge-base/:id"
          element={
            <ProtectedRoute requiredModule="tickets">
              <KnowledgeBaseArticle />
            </ProtectedRoute>
          }
        />
        <Route
          path="/knowledge-base/:id/edit"
          element={
            <ProtectedRoute requiredModule="tickets">
              <KBArticleEdit />
            </ProtectedRoute>
          }
        />
        <Route
          path="/knowledge-base/settings"
          element={
            <ProtectedRoute requiredModule="tickets">
              <KBSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/zones"
          element={
            <ProtectedRoute requiredModule="tickets">
              <ZonesUnified />
            </ProtectedRoute>
          }
        />
        <Route
          path="/zones/new"
          element={
            <ProtectedRoute requiredModule="tickets">
              <ZoneNew />
            </ProtectedRoute>
          }
        />
        <Route
          path="/zones/:id"
          element={
            <ProtectedRoute requiredModule="tickets">
              <ZoneDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/zones/:id/edit"
          element={
            <ProtectedRoute requiredModule="tickets">
              <ZoneEdit />
            </ProtectedRoute>
          }
        />
        {/* Redirect old zone-status route to zones */}
        <Route
          path="/zone-status"
          element={<Navigate to="/zones" replace />}
        />
        <Route path="/slas" element={<PlaceholderPage title="Service Level Agreements" />} />

        {/* Admin routes */}
        <Route
          path="/users"
          element={
            <ProtectedRoute requiredModule="users">
              <Users />
            </ProtectedRoute>
          }
        />

        {/* Profile route - accessible to all authenticated users */}
        <Route path="/profile" element={<MyProfile />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/contract-templates" element={<ContractTemplates />} />
        <Route path="/system-status" element={<PlaceholderPage title="System Status" />} />

        {/* Mobile more page */}
        <Route path="/more" element={<PlaceholderPage title="More Options" />} />
      </Route>
    </Routes>
  );
}

export default App;