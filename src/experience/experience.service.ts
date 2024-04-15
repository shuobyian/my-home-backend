import {
  BadRequestException,
  Inject,
  Injectable,
  forwardRef,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { ReadExperienceDto } from 'src/experience/dto/read-experience-dto';
import { ReadWalnutDto } from 'src/experience/dto/read-walnut-dto';
import { Experience } from 'src/experience/entities/experience.entity';
import { ResultService } from 'src/result/result.service';
import { parseResult } from 'src/result/util/parseResults';
import { DataSource, Repository } from 'typeorm';

@Injectable()
export class ExperienceService {
  constructor(
    private dataSource: DataSource,
    @InjectRepository(Experience)
    private readonly experience: Repository<Experience>,
    @Inject(forwardRef(() => ResultService))
    private resultService: ResultService,
  ) {}

  findAll(): Promise<ReadExperienceDto[]> {
    return this.experience.find();
  }

  async walnut(
    _presentLevel: number,
    _presentExperience?: number,
    _objectiveLevel?: number,
    _productionPercent?: number,
  ): Promise<ReadWalnutDto> {
    const presentLevel = Number(_presentLevel);

    if (presentLevel < 55) {
      throw new BadRequestException(
        '호두나무는 55렙 이상부터 생산 가능합니다. 레벨업하고 오세요.',
      );
    }

    const objectiveLevel = _objectiveLevel ?? presentLevel + 1;
    const presentExperience = _presentExperience
      ? Number(_presentExperience)
      : 0;
    const productionPercent = _productionPercent
      ? Number(_productionPercent)
      : 19;

    const levelArr = Array.from(
      { length: objectiveLevel - presentLevel + 1 },
      (_, index) => presentLevel + index,
    );

    let totalExperience = 0;
    if (objectiveLevel - presentLevel < 2) {
      const experience = await this.experience.findOne({
        where: { level: presentLevel },
      });
      if (experience.amount <= presentExperience) {
        throw new BadRequestException(
          '입력한 경험치가 현재 레벨 경험치보다 많습니다. 다시 설정해 주세요.',
        );
      }
      totalExperience += experience.amount;
    } else {
      for (const level of levelArr) {
        const experience = await this.experience.findOne({
          where: { level },
        });
        totalExperience += experience.amount;
      }
    }

    const walnutExperience = 65340;
    const finalWalnutExperience = parseInt(
      String(walnutExperience * (1 + productionPercent / 100)),
      10,
    );

    const remindExperience = totalExperience - presentExperience;

    const remindCount = parseInt(
      String(remindExperience / finalWalnutExperience),
      10,
    );

    const item = await this.resultService.find('식물앰플-중급 가속');

    return {
      remindExperience,
      remindCount,
      ample: { result: parseResult(item, remindCount) },
    };
  }
}
