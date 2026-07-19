export const showToast = (message: string) => ({ type: 'ui/showToast', payload: message });
export const clearToast = () => ({ type: 'ui/clearToast' });

export default function uiReducer(state = { toast: '' }) {
  return state;
}
