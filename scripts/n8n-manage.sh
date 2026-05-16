#!/bin/bash

# n8n Management Script
# Helper script for managing n8n deployment on Kubernetes

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="n8n"
RELEASE_NAME="n8n"
PORT=5678

# Functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if n8n is deployed
check_deployment() {
    if kubectl get deployment -n $NAMESPACE $RELEASE_NAME &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Status command
status() {
    print_header "n8n Deployment Status"
    
    if ! check_deployment; then
        print_error "n8n is not deployed"
        exit 1
    fi
    
    echo "Namespace: $NAMESPACE"
    echo "Release: $RELEASE_NAME"
    echo ""
    
    print_info "Pods:"
    kubectl get pods -n $NAMESPACE
    echo ""
    
    print_info "Services:"
    kubectl get svc -n $NAMESPACE
    echo ""
    
    print_info "Deployment:"
    kubectl get deployment -n $NAMESPACE
    echo ""
}

# Logs command
logs() {
    print_header "n8n Logs"
    
    if ! check_deployment; then
        print_error "n8n is not deployed"
        exit 1
    fi
    
    kubectl logs -n $NAMESPACE deployment/$RELEASE_NAME --tail=100 -f
}

# Port-forward command
port_forward() {
    print_header "Setting up Port Forward"
    
    if ! check_deployment; then
        print_error "n8n is not deployed"
        exit 1
    fi
    
    # Kill existing port-forward if any
    pkill -f "kubectl port-forward.*$NAMESPACE.*$RELEASE_NAME" 2>/dev/null || true
    
    print_info "Starting port-forward on localhost:$PORT"
    print_success "n8n will be accessible at http://localhost:$PORT"
    print_warning "Press Ctrl+C to stop port-forwarding"
    echo ""
    
    kubectl port-forward -n $NAMESPACE svc/$RELEASE_NAME $PORT:80
}

# Restart command
restart() {
    print_header "Restarting n8n"
    
    if ! check_deployment; then
        print_error "n8n is not deployed"
        exit 1
    fi
    
    kubectl rollout restart deployment/$RELEASE_NAME -n $NAMESPACE
    print_success "Restart initiated"
    
    print_info "Waiting for rollout to complete..."
    kubectl rollout status deployment/$RELEASE_NAME -n $NAMESPACE
    print_success "Restart complete"
}

# Scale command
scale() {
    local replicas=$1
    
    if [ -z "$replicas" ]; then
        print_error "Please specify number of replicas"
        echo "Usage: $0 scale <replicas>"
        exit 1
    fi
    
    print_header "Scaling n8n to $replicas replicas"
    
    if ! check_deployment; then
        print_error "n8n is not deployed"
        exit 1
    fi
    
    kubectl scale deployment/$RELEASE_NAME -n $NAMESPACE --replicas=$replicas
    print_success "Scaled to $replicas replicas"
}

# Upgrade command
upgrade() {
    print_header "Upgrading n8n"
    
    if ! check_deployment; then
        print_error "n8n is not deployed"
        exit 1
    fi
    
    if [ ! -f "kubernetes/n8n/values.yaml" ]; then
        print_error "values.yaml not found at kubernetes/n8n/values.yaml"
        exit 1
    fi
    
    helm upgrade $RELEASE_NAME oci://8gears.container-registry.com/library/n8n \
        --namespace $NAMESPACE \
        --values kubernetes/n8n/values.yaml
    
    print_success "Upgrade complete"
}

# Uninstall command
uninstall() {
    print_header "Uninstalling n8n"
    
    if ! check_deployment; then
        print_error "n8n is not deployed"
        exit 1
    fi
    
    read -p "Are you sure you want to uninstall n8n? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_warning "Uninstall cancelled"
        exit 0
    fi
    
    helm uninstall $RELEASE_NAME -n $NAMESPACE
    print_success "n8n uninstalled"
    
    read -p "Delete namespace $NAMESPACE? (yes/no): " delete_ns
    if [ "$delete_ns" == "yes" ]; then
        kubectl delete namespace $NAMESPACE
        print_success "Namespace deleted"
    fi
}

# Access command
access() {
    print_header "n8n Access Information"
    
    if ! check_deployment; then
        print_error "n8n is not deployed"
        exit 1
    fi
    
    echo "To access n8n, run:"
    echo ""
    echo "  $0 port-forward"
    echo ""
    echo "Then open your browser to:"
    echo "  http://localhost:$PORT"
    echo ""
    
    # Check if port-forward is already running
    if pgrep -f "kubectl port-forward.*$NAMESPACE.*$RELEASE_NAME" > /dev/null; then
        print_success "Port-forward is already running"
        print_info "n8n is accessible at http://localhost:$PORT"
    else
        print_warning "Port-forward is not running"
    fi
}

# Help command
help() {
    echo "n8n Management Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  status        Show deployment status"
    echo "  logs          Show and follow logs"
    echo "  port-forward  Set up port forwarding to access n8n"
    echo "  restart       Restart the deployment"
    echo "  scale <n>     Scale to n replicas"
    echo "  upgrade       Upgrade n8n deployment"
    echo "  uninstall     Uninstall n8n"
    echo "  access        Show access information"
    echo "  help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 status"
    echo "  $0 logs"
    echo "  $0 port-forward"
    echo "  $0 scale 2"
    echo ""
}

# Main
case "${1:-help}" in
    status)
        status
        ;;
    logs)
        logs
        ;;
    port-forward|pf)
        port_forward
        ;;
    restart)
        restart
        ;;
    scale)
        scale "$2"
        ;;
    upgrade)
        upgrade
        ;;
    uninstall)
        uninstall
        ;;
    access)
        access
        ;;
    help|--help|-h)
        help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        help
        exit 1
        ;;
esac

# Made with Bob
