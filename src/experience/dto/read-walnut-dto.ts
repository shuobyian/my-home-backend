import { ReadResultDto } from 'src/result/dto/read-result-dto';

export class ReadWalnutDto {
  remindExperience: number;
  remindCount: number;
  ample: { result: ReadResultDto };
}
