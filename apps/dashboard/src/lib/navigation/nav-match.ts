export class NavMatch {
  static isActive(path: string, to: string, exact: boolean) {
    return exact ? path === to : path === to || path.startsWith(`${to}/`);
  }
}
