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
import Settings from './pages/Settings';
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
        <Route path="/campaigns" element={<PlaceholderPage title="Marketing Campaigns" />} />
        <Route path="/email-templates" element={<PlaceholderPage title="Email Templates" />} />
        <Route path="/analytics" element={<PlaceholderPage title="Marketing Analytics" />} />
        <Route path="/segments" element={<PlaceholderPage title="Customer Segments" />} />

        {/* Tech Support routes */}
        <Route path="/tickets" element={<PlaceholderPage title="Support Tickets" />} />
        <Route path="/knowledge-base" element={<PlaceholderPage title="Knowledge Base" />} />
        <Route path="/equipment" element={<PlaceholderPage title="Equipment Management" />} />
        <Route path="/slas" element={<PlaceholderPage title="Service Level Agreements" />} />

        {/* Admin routes */}
        <Route path="/users" element={<PlaceholderPage title="User Management" />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/audit-logs" element={<PlaceholderPage title="Audit Logs" />} />
        <Route path="/system-status" element={<PlaceholderPage title="System Status" />} />

        {/* Mobile more page */}
        <Route path="/more" element={<PlaceholderPage title="More Options" />} />
      </Route>
    </Routes>
  );
}

export default App;